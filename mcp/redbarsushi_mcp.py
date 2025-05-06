"""
MCP server for RedBarSushiAI.

This server provides tools for setting up a Docker environment matching the staging environment,
with its own Redis and PostgreSQL databases for testing and debugging. It follows the pattern
from the mcp-crawl4ai-rag reference implementation.
"""
from mcp.server.fastmcp import FastMCP, Context
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
import logging
import asyncio
import json
import os
import sys
import subprocess
import tempfile
import datetime
import time
import uuid
import re
import redis
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/app/redbarsushi_mcp.log' if os.environ.get('CONTAINER_MODE') else 'redbarsushi_mcp.log')
    ]
)
logger = logging.getLogger('redbarsushi_mcp')

# Load environment variables from the project root .env file
project_root = Path(__file__).resolve().parent.parent
dotenv_path = project_root / '.env'

# Force override of existing environment variables
if dotenv_path.exists():
    load_dotenv(dotenv_path, override=True)
    logger.info(f"Loaded environment from {dotenv_path}")
else:
    logger.warning(f"No .env file found at {dotenv_path}")

# Create a dataclass for our application context
@dataclass
class RedBarSushiContext:
    """Context for the RedBarSushi MCP server."""
    db_session: Optional[Session] = None
    redis_client: Optional[redis.Redis] = None
    docker_client: Optional[Any] = None
    env_status: Dict[str, Any] = None

@asynccontextmanager
async def redbarsushi_lifespan(server: FastMCP) -> AsyncIterator[RedBarSushiContext]:
    """
    Manages the RedBarSushi context lifecycle.
    
    Args:
        server: The FastMCP server instance
        
    Yields:
        RedBarSushiContext: The context containing database, Redis, and Docker connections
    """
    logger.info("Initializing RedBarSushi MCP server context")
    
    # Initialize connections
    db_session = None
    redis_client = None
    docker_client = None
    env_status = {
        "database": "unavailable",
        "redis": "unavailable",
        "docker": "unavailable",
        "services": {},
        "started_at": datetime.datetime.now().isoformat()
    }
    
    # Configure database connection
    DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/redbarsushi")
    try:
        engine = create_engine(DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db_session = SessionLocal()
        # Test connection
        db_session.execute(text("SELECT 1"))
        logger.info(f"Database connection established: {DATABASE_URL}")
        env_status["database"] = "connected"
    except Exception as e:
        logger.error(f"Database connection error: {str(e)}")
        logger.warning("Running without database support")
    
    # Configure Redis connection
    REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    try:
        redis_client = redis.from_url(REDIS_URL)
        redis_client.ping()  # Check connection
        logger.info(f"Redis connection established: {REDIS_URL}")
        env_status["redis"] = "connected"
    except Exception as e:
        logger.error(f"Redis connection error: {str(e)}")
        logger.warning("Running without Redis support")
    
    # Initialize Docker client if needed
    try:
        import docker
        docker_client = docker.from_env()
        version = docker_client.version()
        logger.info(f"Docker connection established: {version.get('Version', 'unknown')}")
        env_status["docker"] = "connected"
        env_status["docker_version"] = version.get('Version', 'unknown')
    except Exception as e:
        logger.error(f"Docker connection error: {str(e)}")
        logger.warning("Running without Docker support")
    
    try:
        # Yield the context
        context = RedBarSushiContext(
            db_session=db_session,
            redis_client=redis_client,
            docker_client=docker_client,
            env_status=env_status
        )
        yield context
    finally:
        # Clean up resources
        if db_session:
            db_session.close()
            logger.info("Database connection closed")
        
        if redis_client:
            redis_client.close()
            logger.info("Redis connection closed")
        
        if docker_client:
            docker_client.close()
            logger.info("Docker connection closed")

# Initialize the MCP server
mcp = FastMCP(
    "redbarsushi-mcp",
    description="MCP server for RedBarSushi AI voice ordering system",
    lifespan=redbarsushi_lifespan,
    host=os.getenv("HOST", "0.0.0.0"),
    port=int(os.getenv("PORT", "4000"))
)

# Basic tools for testing

@mcp.tool()
async def echo(ctx: Context, message: str) -> str:
    """
    Echo a message back (for testing).
    
    Args:
        ctx: The MCP context
        message: The message to echo
        
    Returns:
        The message echoed back
    """
    return f"Echo: {message}"

@mcp.tool()
async def get_environment_status(ctx: Context) -> Dict[str, Any]:
    """
    Get the status of the environment components.
    
    Args:
        ctx: The MCP context
        
    Returns:
        Dictionary with status of database, Redis, Docker, and services
    """
    env_status = ctx.request_context.lifespan_context.env_status.copy()
    
    # Update services status if Docker is available
    docker_client = ctx.request_context.lifespan_context.docker_client
    if docker_client:
        try:
            # Get running containers
            containers = docker_client.containers.list()
            for container in containers:
                env_status["services"][container.name] = {
                    "id": container.id,
                    "status": container.status,
                    "image": container.image.tags[0] if container.image.tags else "unknown",
                    "created": container.attrs.get("Created", "unknown")
                }
        except Exception as e:
            logger.error(f"Error getting Docker services: {str(e)}")
    
    # Update database status
    db_session = ctx.request_context.lifespan_context.db_session
    if db_session:
        try:
            # Check connection and get database info
            result = db_session.execute(text("SELECT version()"))
            version = result.scalar()
            env_status["database_version"] = version
            
            # Get table count
            result = db_session.execute(text("""
                SELECT count(*) FROM information_schema.tables 
                WHERE table_schema = 'public'
            """))
            table_count = result.scalar()
            env_status["database_tables"] = table_count
        except Exception as e:
            logger.error(f"Error getting database status: {str(e)}")
            env_status["database"] = "error"
    
    # Update Redis status
    redis_client = ctx.request_context.lifespan_context.redis_client
    if redis_client:
        try:
            # Check connection and get Redis info
            info = redis_client.info()
            env_status["redis_version"] = info.get("redis_version")
            env_status["redis_memory_used"] = info.get("used_memory_human")
            env_status["redis_clients_connected"] = info.get("connected_clients")
        except Exception as e:
            logger.error(f"Error getting Redis status: {str(e)}")
            env_status["redis"] = "error"
    
    return env_status

@mcp.tool()
async def run_test(ctx: Context, test_type: str = "basic") -> Dict[str, Any]:
    """
    Run pytest tests with the specified marker.
    
    Args:
        ctx: The MCP context
        test_type: Test marker to run (basic, menu, order, all)
        
    Returns:
        Dictionary with test results (passed, output)
    """
    import subprocess
    import shlex
    
    logger.info(f"Running test type: {test_type}")
    
    # Prepare the command
    if test_type == "all":
        cmd = "pytest tests/ --maxfail=1 --disable-warnings"
    else:
        cmd = f"pytest tests/ -m {test_type} --maxfail=1 --disable-warnings"
    
    try:
        # Run the command
        proc = subprocess.run(
            shlex.split(cmd),
            capture_output=True, 
            text=True,
            cwd=str(project_root)  # Ensure we run from project root
        )
        
        # Log test outcome
        if proc.returncode == 0:
            logger.info(f"Tests passed for marker: {test_type}")
        else:
            logger.error(f"Tests failed for marker: {test_type}")
            
        # Log test history to a file
        with open(project_root / "mcp_test_history.md", "a") as f:
            f.write(f"\n## {datetime.datetime.now().strftime('%Y-%m-%d %H:%M UTC')} — {test_type}\n")
            f.write(f"{'✅ passed' if proc.returncode == 0 else '❌ failed'}\n")
            if proc.returncode != 0:
                # Add the first few lines of the traceback
                error_lines = proc.stdout.strip().split('\n')
                error_lines.extend(proc.stderr.strip().split('\n'))
                error_sample = "\n".join(error_lines[:10])  # First 10 lines of output
                f.write(f"```\n{error_sample}\n```\n")
        
        return {
            "passed": proc.returncode == 0,
            "output": proc.stdout + proc.stderr
        }
    except Exception as e:
        logger.error(f"Error running tests: {str(e)}")
        return {
            "passed": False,
            "output": f"Error running tests: {str(e)}"
        }

# Docker environment management tools

@mcp.tool()
async def setup_docker_environment(
    ctx: Context, 
    environment: str = "staging", 
    force_recreate: bool = False
) -> Dict[str, Any]:
    """
    Set up a Docker environment matching the specified environment (staging or production).
    
    Args:
        ctx: The MCP context
        environment: Environment to set up (staging or production)
        force_recreate: Force recreation of containers even if they exist
        
    Returns:
        Dictionary with setup results
    """
    docker_client = ctx.request_context.lifespan_context.docker_client
    
    if not docker_client:
        return {
            "success": False,
            "message": "Docker connection not available",
            "environment": environment
        }
    
    try:
        # Define the Docker Compose command
        env_vars = {
            "POSTGRES_PASSWORD": "postgres",
            "REDIS_PORT": "6379",
            "POSTGRES_PORT": "5432",
            "MCP_PORT": "4000"
        }
        
        # Add environment-specific variables
        if environment == "production":
            env_vars.update({
                "ENVIRONMENT": "production",
                "DEBUG": "False",
                "LOG_LEVEL": "WARNING"
            })
        else:  # staging or default
            env_vars.update({
                "ENVIRONMENT": "staging",
                "DEBUG": "True",
                "LOG_LEVEL": "INFO"
            })
        
        # Use tempfile to create a temporary environment file
        compose_env_file = tempfile.NamedTemporaryFile(mode='w+', delete=False)
        try:
            # Write environment variables to the file
            for key, value in env_vars.items():
                compose_env_file.write(f"{key}={value}\n")
            compose_env_file.close()
            
            # Prepare Docker Compose command
            compose_file = str(project_root / "docker-compose.yml")
            
            # Check if containers exist and are running
            existing_containers = docker_client.containers.list(
                all=True, 
                filters={"label": "com.docker.compose.project=redbarsushiai"}
            )
            
            if existing_containers and not force_recreate:
                # Stop and remove existing containers if they exist
                logger.info(f"Found {len(existing_containers)} existing containers")
                
                # Check if they're running
                running_containers = [c for c in existing_containers if c.status == 'running']
                
                if running_containers:
                    return {
                        "success": True,
                        "message": f"Environment already running with {len(running_containers)} containers",
                        "environment": environment,
                        "containers": [{
                            "name": c.name,
                            "id": c.id,
                            "status": c.status,
                            "image": c.image.tags[0] if c.image.tags else "unknown"
                        } for c in running_containers]
                    }
            
            # Run Docker Compose
            cmd = [
                "docker-compose",
                "-f", compose_file,
                "--env-file", compose_env_file.name,
                "-p", "redbarsushiai",
                "up", "-d"
            ]
            
            if force_recreate:
                cmd.append("--force-recreate")
            
            logger.info(f"Running Docker Compose command: {' '.join(cmd)}")
            process = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            
            # Wait for containers to be ready
            logger.info("Waiting for containers to be ready...")
            time.sleep(5)  # Give containers time to initialize
            
            # Get running containers
            containers = docker_client.containers.list(
                filters={"label": "com.docker.compose.project=redbarsushiai"}
            )
            
            return {
                "success": True,
                "message": f"Environment set up successfully with {len(containers)} containers",
                "environment": environment,
                "containers": [{
                    "name": c.name,
                    "id": c.id,
                    "status": c.status,
                    "image": c.image.tags[0] if c.image.tags else "unknown"
                } for c in containers],
                "stdout": process.stdout,
                "stderr": process.stderr
            }
        
        finally:
            # Clean up the temporary file
            if compose_env_file:
                os.unlink(compose_env_file.name)
    
    except Exception as e:
        logger.error(f"Error setting up Docker environment: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to set up environment: {str(e)}",
            "environment": environment
        }

@mcp.tool()
async def stop_docker_environment(ctx: Context, remove_volumes: bool = False) -> Dict[str, Any]:
    """
    Stop the Docker environment.
    
    Args:
        ctx: The MCP context
        remove_volumes: Whether to remove volumes (data) as well
        
    Returns:
        Dictionary with stop results
    """
    docker_client = ctx.request_context.lifespan_context.docker_client
    
    if not docker_client:
        return {
            "success": False,
            "message": "Docker connection not available"
        }
    
    try:
        # Prepare Docker Compose command
        compose_file = str(project_root / "docker-compose.yml")
        
        cmd = [
            "docker-compose",
            "-f", compose_file,
            "-p", "redbarsushiai",
            "down"
        ]
        
        if remove_volumes:
            cmd.append("-v")
        
        logger.info(f"Running Docker Compose command: {' '.join(cmd)}")
        process = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        
        return {
            "success": True,
            "message": "Environment stopped successfully",
            "removed_volumes": remove_volumes,
            "stdout": process.stdout,
            "stderr": process.stderr
        }
    
    except Exception as e:
        logger.error(f"Error stopping Docker environment: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to stop environment: {str(e)}"
        }

@mcp.tool()
async def view_container_logs(ctx: Context, container_name: str, lines: int = 100) -> Dict[str, Any]:
    """
    View logs for a specific container.
    
    Args:
        ctx: The MCP context
        container_name: Name of the container to view logs for
        lines: Number of log lines to retrieve
        
    Returns:
        Dictionary with container logs
    """
    docker_client = ctx.request_context.lifespan_context.docker_client
    
    if not docker_client:
        return {
            "success": False,
            "message": "Docker connection not available"
        }
    
    try:
        # Get the container by name
        containers = docker_client.containers.list(
            all=True,
            filters={"name": container_name}
        )
        
        if not containers:
            return {
                "success": False,
                "message": f"Container '{container_name}' not found"
            }
        
        container = containers[0]
        
        # Get container logs
        logs = container.logs(tail=lines).decode('utf-8')
        
        return {
            "success": True,
            "container": container_name,
            "logs": logs,
            "lines": lines
        }
    
    except Exception as e:
        logger.error(f"Error viewing container logs: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to view logs: {str(e)}"
        }

# Restaurant information tools

@mcp.tool()
async def get_restaurant_info(ctx: Context) -> Dict[str, Any]:
    """
    Get information about the restaurant.
    
    Args:
        ctx: The MCP context
        
    Returns:
        Dictionary with restaurant information
    """
    # Static restaurant information
    info = {
        "name": "Red Bar Sushi",
        "address": "123 Main St, Anytown, USA",
        "phone": "+1-555-123-4567",
        "hours": {
            "Monday": "11:00 AM - 10:00 PM",
            "Tuesday": "11:00 AM - 10:00 PM",
            "Wednesday": "11:00 AM - 10:00 PM",
            "Thursday": "11:00 AM - 10:00 PM",
            "Friday": "11:00 AM - 11:00 PM",
            "Saturday": "12:00 PM - 11:00 PM",
            "Sunday": "12:00 PM - 9:00 PM"
        },
        "delivery_radius": "5 miles",
        "minimum_order": "$15.00",
        "delivery_fee": "$3.99"
    }
    
    return info

# Database diagnostics tools

@mcp.tool()
async def get_database_schema(ctx: Context) -> Dict[str, Any]:
    """
    Get the database schema.
    
    Args:
        ctx: The MCP context
        
    Returns:
        Dictionary with database schema information
    """
    db_session = ctx.request_context.lifespan_context.db_session
    
    if not db_session:
        return {
            "success": False,
            "message": "Database connection not available"
        }
    
    try:
        # Get tables
        tables_query = text("""
            SELECT 
                table_name, 
                (SELECT count(*) FROM information_schema.columns WHERE table_name=t.table_name) as column_count
            FROM 
                information_schema.tables t
            WHERE 
                table_schema = 'public'
            ORDER BY 
                table_name
        """)
        tables_result = db_session.execute(tables_query)
        
        tables = []
        for row in tables_result:
            table_name, column_count = row
            
            # Get columns for this table
            columns_query = text("""
                SELECT 
                    column_name, 
                    data_type, 
                    is_nullable, 
                    column_default
                FROM 
                    information_schema.columns
                WHERE 
                    table_schema = 'public' AND table_name = :table_name
                ORDER BY 
                    ordinal_position
            """)
            columns_result = db_session.execute(columns_query, {"table_name": table_name})
            
            columns = []
            for col_row in columns_result:
                columns.append({
                    "name": col_row[0],
                    "data_type": col_row[1],
                    "is_nullable": col_row[2],
                    "default": col_row[3]
                })
            
            # Get row count
            try:
                row_count_query = text(f"SELECT COUNT(*) FROM {table_name}")
                row_count_result = db_session.execute(row_count_query)
                row_count = row_count_result.scalar()
            except:
                row_count = "error"
            
            tables.append({
                "name": table_name,
                "columns": columns,
                "row_count": row_count
            })
        
        return {
            "success": True,
            "tables": tables
        }
    
    except Exception as e:
        logger.error(f"Error getting database schema: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to get database schema: {str(e)}"
        }

@mcp.tool()
async def execute_query(ctx: Context, query: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Execute a SQL query against the database.
    WARNING: This allows executing arbitrary SQL - use only for diagnostics and debugging!
    
    Args:
        ctx: The MCP context
        query: SQL query to execute
        params: Optional parameters for the query
        
    Returns:
        Dictionary with query results
    """
    db_session = ctx.request_context.lifespan_context.db_session
    
    if not db_session:
        return {
            "success": False,
            "message": "Database connection not available"
        }
    
    if params is None:
        params = {}
    
    # Block potentially dangerous queries
    dangerous_patterns = [
        r"\bDROP\b",
        r"\bDELETE\b",
        r"\bTRUNCATE\b",
        r"\bALTER\b",
        r"\bCREATE\b",
        r"\bINSERT\b",
        r"\bUPDATE\b"
    ]
    
    for pattern in dangerous_patterns:
        if re.search(pattern, query, re.IGNORECASE):
            return {
                "success": False,
                "message": f"Potentially dangerous query detected with pattern {pattern}. For safety, only SELECT queries are allowed."
            }
    
    try:
        # Execute the query
        query_text = text(query)
        result = db_session.execute(query_text, params)
        
        # Check if it's a SELECT query
        if result.returns_rows:
            # Convert to list of dictionaries
            column_names = result.keys()
            rows = []
            for row in result:
                row_dict = {}
                for i, column in enumerate(column_names):
                    if isinstance(row[i], (datetime.datetime, datetime.date)):
                        row_dict[column] = row[i].isoformat()
                    else:
                        row_dict[column] = row[i]
                rows.append(row_dict)
            
            return {
                "success": True,
                "columns": list(column_names),
                "rows": rows,
                "row_count": len(rows)
            }
        else:
            return {
                "success": True,
                "message": "Query executed successfully (no rows returned)",
                "rowcount": result.rowcount
            }
    
    except Exception as e:
        logger.error(f"Error executing query: {str(e)}")
        return {
            "success": False,
            "message": f"Query execution failed: {str(e)}"
        }

# Redis diagnostics tools

@mcp.tool()
async def get_redis_keys(ctx: Context, pattern: str = "*", limit: int = 100) -> Dict[str, Any]:
    """
    Get keys from Redis matching the given pattern.
    
    Args:
        ctx: The MCP context
        pattern: Pattern to match keys against
        limit: Maximum number of keys to return
        
    Returns:
        Dictionary with matching Redis keys
    """
    redis_client = ctx.request_context.lifespan_context.redis_client
    
    if not redis_client:
        return {
            "success": False,
            "message": "Redis connection not available"
        }
    
    try:
        # Get keys matching pattern
        keys = redis_client.keys(pattern)
        
        # Limit number of keys
        if len(keys) > limit:
            truncated = True
            keys = keys[:limit]
        else:
            truncated = False
        
        # Convert bytes to strings
        keys = [key.decode('utf-8') if isinstance(key, bytes) else key for key in keys]
        
        return {
            "success": True,
            "keys": keys,
            "count": len(keys),
            "truncated": truncated,
            "pattern": pattern
        }
    
    except Exception as e:
        logger.error(f"Error getting Redis keys: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to get Redis keys: {str(e)}"
        }

@mcp.tool()
async def get_redis_value(ctx: Context, key: str) -> Dict[str, Any]:
    """
    Get the value of a Redis key.
    
    Args:
        ctx: The MCP context
        key: Redis key to get
        
    Returns:
        Dictionary with Redis key value
    """
    redis_client = ctx.request_context.lifespan_context.redis_client
    
    if not redis_client:
        return {
            "success": False,
            "message": "Redis connection not available"
        }
    
    try:
        # Get key type
        key_type = redis_client.type(key).decode('utf-8')
        
        # Get value based on type
        if key_type == "string":
            value = redis_client.get(key)
            if value:
                try:
                    # Try to parse as JSON
                    value = json.loads(value)
                    is_json = True
                except:
                    # Not JSON, decode as string
                    value = value.decode('utf-8') if isinstance(value, bytes) else value
                    is_json = False
            
            return {
                "success": True,
                "key": key,
                "type": key_type,
                "value": value,
                "is_json": is_json
            }
        
        elif key_type == "hash":
            hash_value = redis_client.hgetall(key)
            # Convert bytes to strings in hash
            decoded_hash = {}
            for k, v in hash_value.items():
                decoded_k = k.decode('utf-8') if isinstance(k, bytes) else k
                try:
                    # Try to parse value as JSON
                    decoded_v = json.loads(v) if isinstance(v, bytes) else v
                except:
                    # Not JSON, decode as string
                    decoded_v = v.decode('utf-8') if isinstance(v, bytes) else v
                
                decoded_hash[decoded_k] = decoded_v
            
            return {
                "success": True,
                "key": key,
                "type": key_type,
                "value": decoded_hash
            }
        
        elif key_type == "list":
            list_values = redis_client.lrange(key, 0, -1)
            # Convert bytes to strings in list
            decoded_list = []
            for item in list_values:
                try:
                    # Try to parse as JSON
                    decoded_item = json.loads(item)
                except:
                    # Not JSON, decode as string
                    decoded_item = item.decode('utf-8') if isinstance(item, bytes) else item
                
                decoded_list.append(decoded_item)
            
            return {
                "success": True,
                "key": key,
                "type": key_type,
                "value": decoded_list,
                "length": len(decoded_list)
            }
        
        elif key_type == "set":
            set_values = redis_client.smembers(key)
            # Convert bytes to strings in set
            decoded_set = []
            for item in set_values:
                decoded_item = item.decode('utf-8') if isinstance(item, bytes) else item
                decoded_set.append(decoded_item)
            
            return {
                "success": True,
                "key": key,
                "type": key_type,
                "value": decoded_set,
                "length": len(decoded_set)
            }
        
        elif key_type == "zset":
            zset_values = redis_client.zrange(key, 0, -1, withscores=True)
            # Convert bytes to strings in zset
            decoded_zset = []
            for item, score in zset_values:
                decoded_item = item.decode('utf-8') if isinstance(item, bytes) else item
                decoded_zset.append({"value": decoded_item, "score": score})
            
            return {
                "success": True,
                "key": key,
                "type": key_type,
                "value": decoded_zset,
                "length": len(decoded_zset)
            }
        
        else:
            return {
                "success": False,
                "message": f"Unsupported Redis key type: {key_type}",
                "key": key,
                "type": key_type
            }
    
    except Exception as e:
        logger.error(f"Error getting Redis value: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to get Redis value: {str(e)}",
            "key": key
        }

# Menu management tools

@mcp.tool()
async def lookup_menu_item(ctx: Context, item_name: str, check_availability: bool = True) -> Dict[str, Any]:
    """
    Look up a menu item by name using multiple matching strategies.
    
    Args:
        ctx: The MCP context
        item_name: The name of the item to find
        check_availability: Only return available items if True
        
    Returns:
        Dictionary with the matched menu item or error information
    """
    db_session = ctx.request_context.lifespan_context.db_session
    
    if not db_session:
        return {"success": False, "error": "Database connection not available"}
    
    try:
        # Import here to avoid circular import issues
        from app.utils.menu_utils import find_menu_item_by_name
        
        # Find the menu item
        item = find_menu_item_by_name(item_name, check_availability)
        
        if not item:
            return {
                "success": False,
                "error": f"No menu item found matching '{item_name}'",
                "item_name": item_name
            }
        
        # Format the found item
        return {
            "success": True,
            "item": {
                "name": item.get("name", ""),
                "price": item.get("price", 0),
                "description": item.get("description", ""),
                "plu": item.get("plu", ""),
                "available": item.get("available", True) and not item.get("snoozed", False),
                "category": item.get("category", "")
            }
        }
    except Exception as e:
        logger.error(f"Error looking up menu item: {str(e)}")
        return {"success": False, "error": str(e), "item_name": item_name}

@mcp.tool()
async def get_menu_categories(ctx: Context) -> List[Dict[str, Any]]:
    """
    Get menu categories from the database.
    
    Args:
        ctx: The MCP context
        
    Returns:
        List of menu categories
    """
    # Get database session from context
    db_session = ctx.request_context.lifespan_context.db_session
    
    if not db_session:
        return []
    
    try:
        # Execute the query
        result = db_session.execute(text("SELECT id, name, description FROM menu_categories"))
        
        # Convert to list of dictionaries
        categories = []
        for row in result:
            categories.append({
                "id": row[0],
                "name": row[1],
                "description": row[2]
            })
        
        return categories
    except Exception as e:
        logger.error(f"Error getting menu categories: {str(e)}")
        return []

@mcp.tool()
async def get_menu_items(ctx: Context, category_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Get menu items from the database.
    
    Args:
        ctx: The MCP context
        category_id: Optional category ID to filter items
        
    Returns:
        List of menu items
    """
    # Get database session from context
    db_session = ctx.request_context.lifespan_context.db_session
    
    if not db_session:
        return []
    
    try:
        # Build the query
        query = "SELECT id, name, description, price, plu FROM menu_items"
        params = {}
        
        if category_id is not None:
            query += " WHERE category_id = :category_id"
            params["category_id"] = category_id
        
        # Execute the query
        result = db_session.execute(text(query), params)
        
        # Convert to list of dictionaries
        items = []
        for row in result:
            items.append({
                "id": row[0],
                "name": row[1],
                "description": row[2],
                "price": row[3],
                "plu": row[4]
            })
        
        return items
    except Exception as e:
        logger.error(f"Error getting menu items: {str(e)}")
        return []

@mcp.tool()
async def search_menu_items(ctx: Context, query: str) -> List[Dict[str, Any]]:
    """
    Search menu items by name or description.
    
    Args:
        ctx: The MCP context
        query: Search query string
        
    Returns:
        List of matching menu items
    """
    # Get database session from context
    db_session = ctx.request_context.lifespan_context.db_session
    
    if not db_session:
        return []
    
    try:
        # Execute the query with ILIKE for case-insensitive search
        sql = text("SELECT id, name, description, price, plu FROM menu_items WHERE name ILIKE :query OR description ILIKE :query")
        result = db_session.execute(sql, {"query": f"%{query}%"})
        
        # Convert to list of dictionaries
        items = []
        for row in result:
            items.append({
                "id": row[0],
                "name": row[1],
                "description": row[2],
                "price": row[3],
                "plu": row[4]
            })
        
        return items
    except Exception as e:
        logger.error(f"Error searching menu items: {str(e)}")
        return []

# Cart management tools

@mcp.tool()
async def get_current_cart(ctx: Context, session_id: str) -> Dict[str, Any]:
    """
    Get the current cart for a session from Redis.
    
    Args:
        ctx: The MCP context
        session_id: The session ID
        
    Returns:
        Dictionary with cart contents
    """
    # Get Redis client from context
    redis_client = ctx.request_context.lifespan_context.redis_client
    
    if not redis_client:
        return {"success": False, "error": "Redis connection not available"}
    
    try:
        # Get cart from Redis
        cart_json = redis_client.get(f"cart:{session_id}")
        
        if not cart_json:
            return {"success": True, "cart": {"items": [], "total_price": 0}}
        
        # Parse JSON
        cart = json.loads(cart_json)
        
        return {"success": True, "cart": cart}
    except Exception as e:
        logger.error(f"Error getting cart: {str(e)}")
        return {"success": False, "error": f"Error getting cart: {str(e)}"}

@mcp.tool()
async def place_order(
    ctx: Context,
    session_id: str,
    customer_details: Dict[str, Any],
    order_type: int = 1,
    delivery_details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Place an order with the Deliverect API.
    
    Args:
        ctx: The MCP context
        session_id: The session ID
        customer_details: Dictionary with customer name, phone, email
        order_type: Order type (1: pickup, 2: delivery)
        delivery_details: Optional delivery address details
        
    Returns:
        Dictionary with order status
    """
    # Get connections from context
    db_session = ctx.request_context.lifespan_context.db_session
    redis_client = ctx.request_context.lifespan_context.redis_client
    
    if not db_session or not redis_client:
        return {"success": False, "error": "Database or Redis connection not available"}
    
    try:
        # Get current cart
        cart_json = redis_client.get(f"cart:{session_id}")
        if not cart_json:
            return {"success": False, "error": "Cart not found or empty"}
        
        cart = json.loads(cart_json)
        if not cart.get("items", []):
            return {"success": False, "error": "Cart is empty"}
        
        # Import Deliverect utilities
        from app.utils.deliverect.orders import create_order_in_deliverect
        
        # Generate a unique channel order ID
        deliverect_channel_order_id = f"RBS-{int(time.time())}-{uuid.uuid4().hex[:8].upper()}"
        
        # Format customer for Deliverect
        customer = {
            "name": customer_details.get("name", ""),
            "phoneNumber": customer_details.get("phone", ""),
            "email": customer_details.get("email", "")
        }
        
        # Prepare delivery address if needed
        delivery_address = None
        if order_type == 2 and delivery_details:
            delivery_address = {
                "street": delivery_details.get("street", ""),
                "city": delivery_details.get("city", ""),
                "postalCode": delivery_details.get("postal_code", ""),
                "region": delivery_details.get("region", ""),
                "country": delivery_details.get("country", "US")
            }
        
        # Convert cart items to Deliverect format
        deliverect_items = []
        for item in cart.get("items", []):
            deliverect_item = {
                "plu": item.get("plu"),
                "name": item.get("name"),
                "price": item.get("price"),
                "quantity": item.get("quantity", 1),
                "subItems": []
            }
            
            # Add modifiers if any
            for modifier in item.get("modifiers", []):
                mod_item = {
                    "plu": modifier.get("plu"),
                    "name": modifier.get("name"),
                    "price": modifier.get("price_change", 0),
                    "quantity": modifier.get("quantity", 1)
                }
                deliverect_item["subItems"].append(mod_item)
            
            deliverect_items.append(deliverect_item)
        
        # Create the order in Deliverect
        result = create_order_in_deliverect(
            channel_order_id=deliverect_channel_order_id,
            order_type=order_type,
            customer=customer,
            items=deliverect_items,
            delivery_address=delivery_address,
        )
        
        if result.get("success"):
            # Order was successfully created in Deliverect
            # Create order in local database
            order_sql = text("""
                INSERT INTO orders 
                (deliverect_channel_order_id, customer_phone, customer_name, order_type, status, total_price, delivery_address)
                VALUES (:order_id, :phone, :name, :order_type, 10, :total, :address)
                RETURNING id
            """)
            
            order_params = {
                "order_id": deliverect_channel_order_id,
                "phone": customer_details.get("phone", ""),
                "name": customer_details.get("name", ""),
                "order_type": order_type,
                "total": cart.get("total_price", 0),
                "address": delivery_address.get("street", "") if delivery_address else None
            }
            
            order_result = db_session.execute(order_sql, order_params)
            order_id = order_result.fetchone()[0]
            
            # Add order items to the database
            for item in cart.get("items", []):
                # Insert order item
                item_sql = text("""
                    INSERT INTO order_items
                    (order_id, menu_item_plu, name, price, quantity)
                    VALUES (:order_id, :plu, :name, :price, :quantity)
                    RETURNING id
                """)
                
                item_params = {
                    "order_id": order_id,
                    "plu": item.get("plu", ""),
                    "name": item.get("name", ""),
                    "price": item.get("price", 0),
                    "quantity": item.get("quantity", 1)
                }
                
                item_result = db_session.execute(item_sql, item_params)
                order_item_id = item_result.fetchone()[0]
                
                # Add modifiers if any
                for modifier in item.get("modifiers", []):
                    mod_sql = text("""
                        INSERT INTO order_item_modifiers
                        (order_item_id, modifier_plu, name, price_change, quantity)
                        VALUES (:item_id, :plu, :name, :price, :quantity)
                    """)
                    
                    mod_params = {
                        "item_id": order_item_id,
                        "plu": modifier.get("plu", ""),
                        "name": modifier.get("name", ""),
                        "price": modifier.get("price_change", 0),
                        "quantity": modifier.get("quantity", 1)
                    }
                    
                    db_session.execute(mod_sql, mod_params)
            
            # Commit the transaction
            db_session.commit()
            
            # Clear the cart
            redis_client.delete(f"cart:{session_id}")
            
            # Schedule order status polling
            await poll_order_status(ctx, order_id, deliverect_channel_order_id)
            
            return {
                "success": True,
                "order_id": order_id,
                "deliverect_channel_order_id": deliverect_channel_order_id,
                "status": "created",
                "total_price": cart.get("total_price", 0),
                "deliverect_response": result
            }
        else:
            return {
                "success": False,
                "error": f"Failed to create order in Deliverect: {result.get('error', 'Unknown error')}",
                "deliverect_response": result
            }
    except Exception as e:
        # Rollback transaction on error
        if db_session:
            db_session.rollback()
        
        logger.error(f"Error placing order: {str(e)}")
        return {"success": False, "error": str(e)}

@mcp.tool()
async def poll_order_status(ctx: Context, order_id: int, channel_order_id: str) -> Dict[str, Any]:
    """
    Poll the Deliverect API for order status updates.
    
    Args:
        ctx: The MCP context
        order_id: The ID of the order in the local database
        channel_order_id: The Deliverect channel order ID
        
    Returns:
        Dictionary with order status
    """
    db_session = ctx.request_context.lifespan_context.db_session
    
    if not db_session:
        return {"success": False, "error": "Database connection not available"}
    
    try:
        # Import Deliverect utilities
        from app.utils.deliverect.orders import get_order_status_from_deliverect
        
        # Poll Deliverect for order status
        result = get_order_status_from_deliverect(channel_order_id)
        
        if result.get("success"):
            # Update order status in local database
            status_code = result.get("status", 10)  # Default to 10 (Received)
            
            update_sql = text("""
                UPDATE orders
                SET status = :status, updated_at = NOW()
                WHERE id = :order_id
                RETURNING id, status
            """)
            
            update_result = db_session.execute(update_sql, {"order_id": order_id, "status": status_code})
            updated = update_result.fetchone()
            
            # Commit the transaction
            db_session.commit()
            
            # Check if this is a terminal status (no need to poll again)
            terminal_statuses = [80, 90, 110]  # Delivered, Rejected, Canceled
            is_terminal = status_code in terminal_statuses
            
            return {
                "success": True,
                "order_id": order_id,
                "status_code": status_code,
                "status_name": get_status_name(status_code),
                "is_terminal": is_terminal,
                "deliverect_response": result
            }
        else:
            return {
                "success": False,
                "error": f"Failed to get order status from Deliverect: {result.get('error', 'Unknown error')}",
                "deliverect_response": result
            }
    except Exception as e:
        # Rollback transaction on error
        if db_session:
            db_session.rollback()
        
        logger.error(f"Error polling order status: {str(e)}")
        return {"success": False, "error": str(e)}

def get_status_name(status_code: int) -> str:
    """Get the human-readable status name from a status code."""
    status_map = {
        10: "Received",
        20: "Accepted",
        30: "In Preparation",
        40: "Prepared",
        70: "Ready for Pickup",
        80: "Delivered/Completed",
        90: "Rejected",
        100: "Cancellation Request",
        110: "Canceled"
    }
    return status_map.get(status_code, "Unknown Status")

@mcp.tool()
async def add_to_cart(
    ctx: Context, 
    session_id: str, 
    item_plu: str, 
    quantity: int = 1, 
    modifiers: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Add an item to the cart in Redis.
    
    Args:
        ctx: The MCP context
        session_id: The session ID
        item_plu: The PLU of the item to add
        quantity: The quantity to add (default: 1)
        modifiers: Optional list of modifiers to add
        
    Returns:
        Dictionary with updated cart
    """
    try:
        # Get connections from context
        db_session = ctx.request_context.lifespan_context.db_session
        redis_client = ctx.request_context.lifespan_context.redis_client
        
        if not db_session or not redis_client:
            return {"success": False, "error": "Database or Redis connection not available"}
        
        # Get item details from database
        sql = text("SELECT id, name, price FROM menu_items WHERE plu = :plu")
        result = db_session.execute(sql, {"plu": item_plu})
        row = result.fetchone()
        
        if not row:
            return {"success": False, "error": f"Item with PLU {item_plu} not found"}
        
        item_id, item_name, item_price = row
        
        # Get current cart from Redis
        cart_json = redis_client.get(f"cart:{session_id}")
        cart = json.loads(cart_json) if cart_json else {"items": [], "total_price": 0}
        
        # Add item to cart
        new_item = {
            "plu": item_plu,
            "name": item_name,
            "price": item_price,
            "quantity": quantity,
            "modifiers": modifiers or []
        }
        
        # Calculate item total price including modifiers
        item_total = item_price * quantity
        for modifier in (modifiers or []):
            if "price_change" in modifier:
                item_total += modifier["price_change"] * quantity
        
        cart["items"].append(new_item)
        cart["total_price"] += item_total
        
        # Save updated cart to Redis
        redis_client.set(f"cart:{session_id}", json.dumps(cart))
        
        return {"success": True, "cart": cart}
    except Exception as e:
        logger.error(f"Error adding to cart: {str(e)}")
        return {"success": False, "error": str(e)}

# Server entry point

async def main():
    """Run the MCP server."""
    logger.info("Starting RedBarSushi MCP server")
    transport = os.getenv("TRANSPORT", "sse")
    
    if transport == 'sse':
        # Run the MCP server with SSE transport
        logger.info("Using SSE transport")
        await mcp.run_sse_async()
    else:
        # Run with Stdio transport by default
        logger.info("Using Stdio transport")
        await mcp.run_stdio_async()

if __name__ == "__main__":
    asyncio.run(main())