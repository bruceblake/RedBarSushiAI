#!/usr/bin/env python3
"""
RedBarSushiAI MCP Server

Provides tools for local debugging, testing, and validation in a staging-parity environment.
Implements the FastMCP JSON-RPC and SSE protocol for interaction with Claude.

- Spins up a Docker environment with Redis, PostgreSQL, and Flask
- Discovers and runs tests
- Provides tools for inspecting and manipulating the system
- Keeps files under 500 lines by design
"""
import os
import sys
import json
import time
import logging
import subprocess
import asyncio
import re
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, AsyncIterator, Tuple
from dataclasses import dataclass
from contextlib import asynccontextmanager
from datetime import datetime
from collections.abc import AsyncIterator

import docker
import redis
import psycopg2
from psycopg2.extras import RealDictCursor
import pytest
from fastmcp import FastMCP, Context

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('mcp_server.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("mcp_server")

# Set up the project root directory
PROJECT_ROOT = Path(__file__).resolve().parent

# Create a dataclass for our application context
@dataclass
class RedBarSushiContext:
    """Context for the RedBarSushi MCP server."""
    redis_client: Optional[redis.Redis] = None
    postgres_conn: Optional[Any] = None
    docker_client: Optional[docker.DockerClient] = None
    celery_app: Optional[Any] = None
    start_time: datetime = datetime.now()

@asynccontextmanager
async def redbarsushi_lifespan(server: FastMCP) -> AsyncIterator[RedBarSushiContext]:
    """
    Manages the RedBarSushi context lifecycle.
    
    Args:
        server: The FastMCP server instance
        
    Yields:
        RedBarSushiContext: The context containing connections to services
    """
    logger.info("Initializing RedBarSushi MCP server context")
    
    # Initialize connections
    redis_client = None
    postgres_conn = None
    docker_client = None
    celery_app = None
    
    # Connect to Redis
    try:
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        redis_client = redis.from_url(redis_url)
        redis_client.ping()  # Check connection
        logger.info(f"Connected to Redis: {redis_url}")
    except Exception as e:
        logger.warning(f"Failed to connect to Redis: {str(e)}")
    
    # Connect to PostgreSQL
    try:
        db_url = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/redbarsushi")
        
        # Parse connection string
        match = re.match(r'postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)', db_url)
        if match:
            user, password, host, port, dbname = match.groups()
            postgres_conn = psycopg2.connect(
                host=host,
                port=port,
                dbname=dbname,
                user=user,
                password=password
            )
            logger.info(f"Connected to PostgreSQL: {host}:{port}/{dbname}")
        else:
            logger.warning(f"Invalid PostgreSQL connection string: {db_url}")
    except Exception as e:
        logger.warning(f"Failed to connect to PostgreSQL: {str(e)}")
    
    # Connect to Docker
    try:
        docker_client = docker.from_env()
        version = docker_client.version()
        logger.info(f"Connected to Docker: {version.get('Version')}")
    except Exception as e:
        logger.warning(f"Failed to connect to Docker: {str(e)}")
    
    # Initialize Celery (deferred import to avoid circular dependency)
    try:
        # We do a simple import check first to avoid the full import if not available
        if importlib_available("celery"):
            from celery import Celery
            from celery_app import app as celery_app_instance
            celery_app = celery_app_instance
            logger.info("Connected to Celery application")
        else:
            logger.warning("Celery module not available")
    except Exception as e:
        logger.warning(f"Failed to initialize Celery: {str(e)}")
    
    try:
        # Create and yield the context
        context = RedBarSushiContext(
            redis_client=redis_client,
            postgres_conn=postgres_conn,
            docker_client=docker_client,
            celery_app=celery_app,
            start_time=datetime.now()
        )
        yield context
    finally:
        # Clean up resources
        logger.info("Cleaning up resources")
        
        if redis_client:
            try:
                redis_client.close()
                logger.info("Redis connection closed")
            except Exception as e:
                logger.error(f"Error closing Redis connection: {str(e)}")
        
        if postgres_conn:
            try:
                postgres_conn.close()
                logger.info("PostgreSQL connection closed")
            except Exception as e:
                logger.error(f"Error closing PostgreSQL connection: {str(e)}")
        
        if docker_client:
            try:
                docker_client.close()
                logger.info("Docker client closed")
            except Exception as e:
                logger.error(f"Error closing Docker client: {str(e)}")

def importlib_available(module_name: str) -> bool:
    """Check if a module can be imported without actually importing it."""
    try:
        __import__(module_name)
        return True
    except ImportError:
        return False

# Initialize MCP server
mcp = FastMCP(
    "redbarsushi-mcp",
    description="MCP server for RedBarSushiAI local testing and debugging",
    lifespan=redbarsushi_lifespan,
    host=os.environ.get("HOST", "0.0.0.0"),
    port=int(os.environ.get("PORT", 11235))
)

#
# 3.1 FOUNDATIONAL TOOLS
#

@mcp.tool()
async def ping(ctx: Context) -> str:
    """
    Simple ping-pong test to verify the MCP server is responsive.
    
    Returns:
        "pong" if successful
    """
    return "pong"

@mcp.tool()
async def service_health(ctx: Context) -> Dict[str, str]:
    """
    Get health status of all services in the environment.
    
    Returns:
        Dictionary with service statuses
    """
    result = {
        "mcp": "ok",
        "redis": "disconnected",
        "postgres": "disconnected",
        "celery": "down",
        "voice_ws": "down"
    }
    
    # Check Redis connection
    redis_client = ctx.request_context.lifespan_context.redis_client
    if redis_client:
        try:
            redis_client.ping()
            result["redis"] = "connected"
        except Exception:
            result["redis"] = "error"
    
    # Check PostgreSQL connection
    postgres_conn = ctx.request_context.lifespan_context.postgres_conn
    if postgres_conn:
        try:
            with postgres_conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            result["postgres"] = "connected"
        except Exception:
            result["postgres"] = "error"
    
    # Check Celery status
    celery_app = ctx.request_context.lifespan_context.celery_app
    if celery_app:
        try:
            # Simple check - can we inspect active workers?
            i = celery_app.control.inspect()
            workers = i.active()
            result["celery"] = "up" if workers else "no_workers"
        except Exception:
            result["celery"] = "error"
    
    # Check WebSocket server for voice
    try:
        # Simple check - just see if the /ws endpoint exists by running curl
        completed_process = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "http://localhost:5000/api/ws/voice"],
            capture_output=True,
            text=True,
            timeout=2
        )
        status_code = completed_process.stdout.strip()
        # WebSockets usually return 400 (bad request) when hit with a normal HTTP GET
        # Any response (even an error) means the endpoint exists
        result["voice_ws"] = "up" if status_code in ["400", "101", "200"] else "down"
    except Exception:
        result["voice_ws"] = "not_checked"
    
    return result

@mcp.tool()
async def container_stats(ctx: Context) -> Dict[str, Any]:
    """
    Get statistics about Docker containers running in the environment.
    
    Returns:
        Dictionary with container statistics
    """
    docker_client = ctx.request_context.lifespan_context.docker_client
    if not docker_client:
        return {"error": "Docker client not available"}
    
    result = {}
    try:
        containers = docker_client.containers.list()
        
        for container in containers:
            stats = container.stats(stream=False)
            
            # Extract CPU stats
            cpu_stats = stats.get("cpu_stats", {})
            precpu_stats = stats.get("precpu_stats", {})
            
            cpu_delta = cpu_stats.get("cpu_usage", {}).get("total_usage", 0) - \
                        precpu_stats.get("cpu_usage", {}).get("total_usage", 0)
            
            system_delta = cpu_stats.get("system_cpu_usage", 0) - \
                           precpu_stats.get("system_cpu_usage", 0)
            
            cpu_usage = 0.0
            if system_delta > 0 and cpu_delta > 0:
                cpu_usage = (cpu_delta / system_delta) * \
                            len(cpu_stats.get("cpu_usage", {}).get("percpu_usage", [1]))
            
            # Extract memory stats
            memory_stats = stats.get("memory_stats", {})
            memory_usage = memory_stats.get("usage", 0)
            memory_limit = memory_stats.get("limit", 1)
            memory_usage_mb = memory_usage / (1024 * 1024)
            memory_percent = (memory_usage / memory_limit) * 100.0
            
            # Get container uptime
            inspection = container.attrs
            started_at = inspection.get("State", {}).get("StartedAt", "")
            if started_at:
                started_time = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                uptime_seconds = (datetime.now().astimezone() - started_time).total_seconds()
                hours, remainder = divmod(int(uptime_seconds), 3600)
                minutes, seconds = divmod(remainder, 60)
                uptime = f"{hours}h{minutes}m{seconds}s"
            else:
                uptime = "unknown"
            
            result[container.name] = {
                "status": container.status,
                "cpu": round(cpu_usage * 100, 2),
                "mem_mb": round(memory_usage_mb, 2),
                "mem_percent": round(memory_percent, 2),
                "uptime": uptime,
                "image": container.image.tags[0] if container.image.tags else "unknown"
            }
    
    except Exception as e:
        logger.error(f"Error getting container stats: {str(e)}")
        return {"error": str(e)}
    
    # Add server uptime
    start_time = ctx.request_context.lifespan_context.start_time
    uptime_seconds = (datetime.now() - start_time).total_seconds()
    hours, remainder = divmod(int(uptime_seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    
    result["mcp_server"] = {
        "status": "running",
        "uptime": f"{hours}h{minutes}m{seconds}s",
        "started_at": start_time.isoformat()
    }
    
    return result

#
# 3.2 TESTING TOOLS
#

@mcp.tool()
async def run_test(ctx: Context, test_type: str = "all", maxfail: int = 1, kcov: bool = False) -> Dict[str, Any]:
    """
    Run pytest tests with the specified marker.
    
    Args:
        ctx: The MCP context
        test_type: Test marker to run (unit, db, webhook, voice, all)
        maxfail: Maximum number of failures before stopping
        kcov: Whether to collect coverage information
        
    Returns:
        Dictionary with test results (passed, output, coverage_pct)
    """
    # Get the coverage data file path
    coverage_file = PROJECT_ROOT / ".coverage"
    
    # Prepare the command
    cmd = ["python", "-m", "pytest"]
    
    # Add coverage option if requested
    if kcov:
        cmd.extend(["--cov=app", "--cov-report=term"])
    
    # Add test type filter
    if test_type != "all":
        cmd.extend(["-m", test_type])
    else:
        cmd.append("tests/")
    
    # Add maxfail option
    cmd.extend(["--maxfail", str(maxfail)])
    
    # Add other options
    cmd.extend(["--disable-warnings", "-v"])
    
    try:
        # Run the command
        start_time = time.time()
        proc = subprocess.run(
            cmd,
            capture_output=True, 
            text=True,
            cwd=str(PROJECT_ROOT)
        )
        end_time = time.time()
        duration = round(end_time - start_time, 2)
        
        # Parse the output
        output = proc.stdout + proc.stderr
        passed = proc.returncode == 0
        
        # Extract coverage percentage if enabled
        coverage_pct = None
        if kcov and passed:
            coverage_match = re.search(r'TOTAL\s+\d+\s+\d+\s+(\d+)%', output)
            if coverage_match:
                coverage_pct = int(coverage_match.group(1))
        
        # Log test outcome
        if passed:
            logger.info(f"Tests passed for type: {test_type}")
        else:
            logger.error(f"Tests failed for type: {test_type}")
            
        # Log test history to a file
        with open(PROJECT_ROOT / "mcp_test_history.md", "a") as f:
            f.write(f"\n## {datetime.now().strftime('%Y-%m-%d %H:%M')} — {test_type}\n")
            f.write(f"{'✅ passed' if passed else '❌ failed'}\n")
            if coverage_pct is not None:
                f.write(f"Coverage: {coverage_pct}%\n")
            f.write(f"Duration: {duration}s\n")
            if not passed:
                # Add the first few failure messages
                failure_lines = [line for line in output.split('\n') if 'FAILED' in line][:5]
                if failure_lines:
                    f.write("```\n")
                    f.write('\n'.join(failure_lines))
                    f.write("\n```\n")
        
        return {
            "passed": passed,
            "output": output,
            "duration": duration,
            "coverage_pct": coverage_pct
        }
    except Exception as e:
        logger.error(f"Error running tests: {str(e)}")
        return {
            "passed": False,
            "output": f"Error running tests: {str(e)}"
        }

@mcp.tool()
async def list_tests(ctx: Context, marker: Optional[str] = None) -> Dict[str, Any]:
    """
    List available tests, optionally filtered by marker.
    
    Args:
        ctx: The MCP context
        marker: Test marker to filter by
        
    Returns:
        Dictionary with list of test nodeids
    """
    cmd = ["python", "-m", "pytest", "--collect-only", "-q"]
    
    # Add marker filter if provided
    if marker:
        cmd.extend(["-m", marker])
    
    try:
        # Run the command
        proc = subprocess.run(
            cmd,
            capture_output=True, 
            text=True,
            cwd=str(PROJECT_ROOT)
        )
        
        # Parse the output to get the list of tests
        output = proc.stdout
        test_nodeids = []
        
        for line in output.strip().split('\n'):
            if line and not line.startswith('=') and not line.startswith('no tests'):
                test_nodeids.append(line.strip())
        
        return {
            "success": True,
            "tests": test_nodeids,
            "count": len(test_nodeids),
            "marker": marker
        }
    except Exception as e:
        logger.error(f"Error listing tests: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

#
# 3.3 DATABASE TOOLS
#

@mcp.tool()
async def sql(ctx: Context, query: str) -> Dict[str, Any]:
    """
    Execute a read-only SQL query against the database.
    
    Args:
        ctx: The MCP context
        query: SQL query to execute (must be SELECT)
        
    Returns:
        Dictionary with query results
    """
    postgres_conn = ctx.request_context.lifespan_context.postgres_conn
    
    if not postgres_conn:
        return {"success": False, "error": "Database connection not available"}
    
    # Ensure query is read-only
    query = query.strip()
    if not query.lower().startswith('select'):
        return {
            "success": False,
            "error": "Only SELECT queries are allowed for security reasons"
        }
    
    try:
        # Execute the query with RealDictCursor to get column names
        with postgres_conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()
            
            # Convert rows to list of dicts
            result = [dict(row) for row in rows]
            
            return {
                "success": True,
                "rows": result,
                "count": len(result)
            }
    except Exception as e:
        logger.error(f"Error executing SQL query: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "query": query
        }

@mcp.tool()
async def menu_item(ctx: Context, plu: str) -> Dict[str, Any]:
    """
    Get details for a menu item by PLU.
    
    Args:
        ctx: The MCP context
        plu: Product Look-Up (PLU) code
        
    Returns:
        Dictionary with menu item details
    """
    postgres_conn = ctx.request_context.lifespan_context.postgres_conn
    
    if not postgres_conn:
        return {"success": False, "error": "Database connection not available"}
    
    try:
        # Get menu item details
        with postgres_conn.cursor(cursor_factory=RealDictCursor) as cursor:
            query = """
                SELECT 
                    mi.*, 
                    mc.name AS category_name
                FROM 
                    menu_items mi
                LEFT JOIN 
                    menu_categories mc ON mi.category_id = mc.id
                WHERE 
                    mi.plu = %s
            """
            cursor.execute(query, (plu,))
            item = cursor.fetchone()
            
            if not item:
                return {"success": False, "error": f"Menu item with PLU '{plu}' not found"}
            
            # Get modifier groups for this item
            query_modifiers = """
                SELECT 
                    mmg.id, mmg.name, mmg.min_selection, mmg.max_selection, mmg.multi_max,
                    mmg.is_variant_group
                FROM 
                    menu_modifier_groups mmg
                JOIN 
                    item_modifier_groups img ON mmg.id = img.modifier_group_id
                WHERE 
                    img.menu_item_id = %s
            """
            cursor.execute(query_modifiers, (item['id'],))
            modifier_groups = cursor.fetchall()
            
            # Get modifiers for each group
            for group in modifier_groups:
                query_group_modifiers = """
                    SELECT 
                        mm.id, mm.name, mm.price_change, mm.plu, mm.is_available,
                        mm.snoozed_until
                    FROM 
                        menu_modifiers mm
                    WHERE 
                        mm.modifier_group_id = %s
                """
                cursor.execute(query_group_modifiers, (group['id'],))
                group['modifiers'] = cursor.fetchall()
            
            # Return full item details
            return {
                "success": True,
                "item": dict(item),
                "modifier_groups": [dict(group) for group in modifier_groups]
            }
    except Exception as e:
        logger.error(f"Error getting menu item: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "plu": plu
        }

@mcp.tool()
async def order_summary(ctx: Context, order_id: int) -> Dict[str, Any]:
    """
    Get summary of an order by ID.
    
    Args:
        ctx: The MCP context
        order_id: Order ID
        
    Returns:
        Dictionary with order details
    """
    postgres_conn = ctx.request_context.lifespan_context.postgres_conn
    
    if not postgres_conn:
        return {"success": False, "error": "Database connection not available"}
    
    try:
        # Get order details
        with postgres_conn.cursor(cursor_factory=RealDictCursor) as cursor:
            query = """
                SELECT * FROM orders WHERE id = %s
            """
            cursor.execute(query, (order_id,))
            order = cursor.fetchone()
            
            if not order:
                return {"success": False, "error": f"Order with ID {order_id} not found"}
            
            # Get order items
            query_items = """
                SELECT * FROM order_items WHERE order_id = %s
            """
            cursor.execute(query_items, (order_id,))
            items = cursor.fetchall()
            
            # Get modifiers for each item
            for item in items:
                query_modifiers = """
                    SELECT * FROM order_item_modifiers WHERE order_item_id = %s
                """
                cursor.execute(query_modifiers, (item['id'],))
                item['modifiers'] = cursor.fetchall()
            
            # Return full order details
            return {
                "success": True,
                "order": dict(order),
                "items": [dict(item) for item in items]
            }
    except Exception as e:
        logger.error(f"Error getting order summary: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "order_id": order_id
        }

#
# 3.4 REDIS TOOLS
#

@mcp.tool()
async def redis_get(ctx: Context, key: str) -> Dict[str, Any]:
    """
    Get value of a Redis key.
    
    Args:
        ctx: The MCP context
        key: Redis key
        
    Returns:
        Dictionary with key value
    """
    redis_client = ctx.request_context.lifespan_context.redis_client
    
    if not redis_client:
        return {"success": False, "error": "Redis connection not available"}
    
    try:
        # Get key type to determine how to read it
        key_type = redis_client.type(key).decode('utf-8')
        
        if key_type == 'none':
            return {"success": False, "error": f"Key '{key}' does not exist"}
        
        if key_type == 'string':
            value = redis_client.get(key)
            
            # Try to decode as JSON
            try:
                value = json.loads(value)
                is_json = True
            except:
                value = value.decode('utf-8') if isinstance(value, bytes) else value
                is_json = False
            
            return {
                "success": True,
                "key": key,
                "type": key_type,
                "value": value,
                "is_json": is_json
            }
        
        elif key_type == 'hash':
            value = redis_client.hgetall(key)
            
            # Convert bytes to strings
            decoded = {}
            for k, v in value.items():
                k = k.decode('utf-8') if isinstance(k, bytes) else k
                
                # Try to decode value as JSON
                try:
                    v = json.loads(v) if isinstance(v, bytes) else v
                except:
                    v = v.decode('utf-8') if isinstance(v, bytes) else v
                
                decoded[k] = v
            
            return {
                "success": True,
                "key": key,
                "type": key_type,
                "value": decoded
            }
        
        elif key_type == 'list':
            items = redis_client.lrange(key, 0, -1)
            
            # Convert bytes to strings
            decoded = []
            for item in items:
                try:
                    item = json.loads(item) if isinstance(item, bytes) else item
                except:
                    item = item.decode('utf-8') if isinstance(item, bytes) else item
                decoded.append(item)
            
            return {
                "success": True,
                "key": key,
                "type": key_type,
                "value": decoded,
                "length": len(decoded)
            }
        
        elif key_type == 'set':
            items = redis_client.smembers(key)
            
            # Convert bytes to strings
            decoded = []
            for item in items:
                try:
                    item = json.loads(item) if isinstance(item, bytes) else item
                except:
                    item = item.decode('utf-8') if isinstance(item, bytes) else item
                decoded.append(item)
            
            return {
                "success": True,
                "key": key,
                "type": key_type,
                "value": decoded,
                "length": len(decoded)
            }
        
        else:
            return {
                "success": False,
                "error": f"Unsupported key type: {key_type}",
                "key": key
            }
    except Exception as e:
        logger.error(f"Error getting Redis key: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "key": key
        }

@mcp.tool()
async def redis_scan(ctx: Context, pattern: str = "*") -> Dict[str, Any]:
    """
    Scan Redis keys matching a pattern.
    
    Args:
        ctx: The MCP context
        pattern: Pattern to match keys
        
    Returns:
        Dictionary with matching keys
    """
    redis_client = ctx.request_context.lifespan_context.redis_client
    
    if not redis_client:
        return {"success": False, "error": "Redis connection not available"}
    
    try:
        # Scan keys matching pattern
        keys = []
        cursor = 0
        count = 0
        
        while True:
            cursor, partial_keys = redis_client.scan(cursor, pattern, 100)
            partial_keys = [k.decode('utf-8') if isinstance(k, bytes) else k for k in partial_keys]
            keys.extend(partial_keys)
            count += len(partial_keys)
            
            if cursor == 0:
                break
        
        return {
            "success": True,
            "pattern": pattern,
            "keys": keys,
            "count": count
        }
    except Exception as e:
        logger.error(f"Error scanning Redis keys: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "pattern": pattern
        }

@mcp.tool()
async def redis_ttl(ctx: Context, key: str) -> Dict[str, Any]:
    """
    Get TTL (time to live) of a Redis key.
    
    Args:
        ctx: The MCP context
        key: Redis key
        
    Returns:
        Dictionary with TTL in seconds
    """
    redis_client = ctx.request_context.lifespan_context.redis_client
    
    if not redis_client:
        return {"success": False, "error": "Redis connection not available"}
    
    try:
        # Check if key exists
        if not redis_client.exists(key):
            return {"success": False, "error": f"Key '{key}' does not exist"}
        
        # Get TTL
        ttl = redis_client.ttl(key)
        
        if ttl == -1:
            return {
                "success": True,
                "key": key,
                "ttl": ttl,
                "expires": False,
                "message": "Key does not expire"
            }
        elif ttl == -2:
            return {
                "success": False,
                "key": key,
                "ttl": ttl,
                "message": "Key does not exist"
            }
        else:
            expires_at = datetime.now() + datetime.timedelta(seconds=ttl)
            return {
                "success": True,
                "key": key,
                "ttl": ttl,
                "expires": True,
                "expires_at": expires_at.isoformat(),
                "expires_in": f"{ttl // 3600}h {(ttl % 3600) // 60}m {ttl % 60}s"
            }
    except Exception as e:
        logger.error(f"Error getting Redis TTL: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "key": key
        }

# Start the MCP server if running as main script
if __name__ == "__main__":
    transport = os.environ.get("TRANSPORT", "sse")
    logger.info(f"Starting RedBarSushi MCP server with {transport} transport")
    
    if transport == "sse":
        asyncio.run(mcp.run_sse_async())
    else:
        asyncio.run(mcp.run_stdio_async())