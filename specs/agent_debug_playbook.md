# Local-Development & Debug Playbook for Autonomous Coding Agents

**Working with the RedBarSushiAI System**  
*(Host-Bridged Container Edition)*

## 0 · Directory Context
You are currently located at the repo root which contains:

```
.
├── app/                    # Flask app, agents, models, utils
│   ├── agents/             # Voice ordering agents and orchestration
│   ├── models/             # Database models for menu and orders
│   ├── routes/             # API endpoints including voice handlers
│   └── utils/              # Shared utilities & SDK components
├── mcp/                    # MCP server components & tools
│   ├── src/                # Source code for MCP server
│   ├── docker/             # MCP Docker configuration
│   └── db/                 # Database initialization scripts
├── docker-compose.yml      # Base container configuration
├── docker-compose.staging.yml  # Staging override configuration
├── mcp_server.py           # MCP server with diagnostic tools
├── run.py                  # Main Flask application entry point
└── tests/                  # Test suites (unit, e2e, integration)
```

All commands should be run from this root directory.

## 1 · Spinning Up the Complete Local Stack

### 1.1 Prepare Environment Variables
```bash
# Copy staging environment variables (skip if .env exists)
cp -n .env.staging .env
```

### 1.2 Launch the Container Stack
```bash
# Build and start all containers in the background
docker-compose -f docker-compose.yml -f docker-compose.staging.yml up --build -d
```

This starts the following containers:
- `redbarsushi_web`: Flask application with the voice system
- `redbarsushi_mcp`: Mission Control Protocol server for diagnostics and tools
- `redbarsushi_postgres`: PostgreSQL database for menu and orders
- `redbarsushi_redis`: Redis for caching, pub/sub and task queue
- `redbarsushi_celery`: Background task worker

All containers are networked together on the `redbarsushi_network`.

### 1.3 Sanity Checks (from host shell)
```bash
# Check MCP server health
curl -sf http://host.docker.internal:4244/health

# Check web application health
curl -sf http://host.docker.internal:5000/healthcheck
```

Both commands should return JSON with `"status":"ok"`.

## 2 · MCP Server Access (Host → Container)

All tool calls are SSE-based requests to:

```
http://host.docker.internal:4244/sse
```

Python helper for making MCP tool calls:

```python
import json
import requests
import sseclient

MCP_URL = "http://host.docker.internal:4244/sse"

def call_mcp_tool(tool_name, **params):
    """Call MCP tool and return the result"""
    # Prepare tool call payload
    tool_call = {
        "name": tool_name,
        "arguments": params
    }
    
    # Make SSE request
    response = requests.get(
        MCP_URL, 
        headers={"Accept": "text/event-stream"},
        params={"tool_call": json.dumps(tool_call)},
        stream=True
    )
    
    # Process SSE response
    client = sseclient.SSEClient(response)
    result = None
    
    for event in client.events():
        data = json.loads(event.data)
        if data.get("type") == "tool_result":
            result = data.get("result")
            break
    
    return result
```

From inside containers, use `http://redbarsushi_mcp:4244/sse` instead of `host.docker.internal`.

## 3 · Essential MCP Tools

| Tool | Typical Call | Purpose |
|------|--------------|---------|
| `container_status` | `call_mcp_tool("container_status", container_name="redbarsushi_web")` | Check container health |
| `fix_db_connection` | `call_mcp_tool("fix_db_connection", container_name="redbarsushi_web")` | Fix database connectivity |
| `fix_redis_db` | `call_mcp_tool("fix_redis_db")` | Fix Redis issues |
| `autonomous_fix_all` | `call_mcp_tool("autonomous_fix_all")` | Automatically fix all containers |
| `http_get` | `call_mcp_tool("http_get", path="/healthcheck")` | Test web endpoints |
| `http_post` | `call_mcp_tool("http_post", path="/api/order", json={...})` | Test POST endpoints |
| `ws_echo` | `call_mcp_tool("ws_echo", message="test")` | Test WebSocket echo |
| `sql` | `call_mcp_tool("sql", query="SELECT * FROM menu_items LIMIT 5")` | Execute SQL queries |
| `redis_get` | `call_mcp_tool("redis_get", key="conversation:123")` | Get Redis values |
| `redis_scan` | `call_mcp_tool("redis_scan", pattern="menu:*")` | List matching Redis keys |
| `container_logs` | `call_mcp_tool("container_logs", container="redbarsushi_web", lines=50)` | View container logs |

## 4 · Testing with MCP

### Running Tests
```python
# Run all tests
result = call_mcp_tool("run_test", test_type="all")

# Run unit tests only
result = call_mcp_tool("run_test", test_type="unit")

# Run a specific test file
result = call_mcp_tool("run_test", test_path="tests/e2e/test_voice_flow.py")

# Run with coverage report
result = call_mcp_tool("run_test", test_type="all", coverage=True)
```

### Listing Available Tests
```python
tests = call_mcp_tool("list_tests")
```

## 5 · Auto-Watcher for TDD

Run the test watcher to automatically execute tests when files change:

```bash
python scripts/watch_tests.py
```

This will monitor the `tests/` directory and run the appropriate tests when files change.

## 6 · Debug & Fix Workflow

1. Run tests to identify issues:
   ```python
   result = call_mcp_tool("run_test", test_type="unit")
   ```

2. Examine failures in the result output:
   ```python
   print(result["output"])
   ```

3. Use MCP tools to inspect the state:
   ```python
   # Check database state
   db_data = call_mcp_tool("sql", query="SELECT * FROM menu_items LIMIT 5")
   
   # Check Redis state
   redis_keys = call_mcp_tool("redis_scan", pattern="menu:*")
   
   # Check container logs
   logs = call_mcp_tool("container_logs", container="redbarsushi_web")
   ```

4. Edit code in the appropriate files under `app/` directory
   - Keep files under 500 lines as per project guidelines
   - Follow existing patterns and conventions

5. Save your changes - containers will automatically reload due to mounted volumes

6. Re-run the failing tests to verify fixes:
   ```python
   result = call_mcp_tool("run_test", test_path="tests/unit/test_failing.py")
   ```

7. Repeat until all tests pass with good coverage:
   ```python
   final_result = call_mcp_tool("run_test", test_type="all", coverage=True)
   # Should show {"passed": True, "coverage_pct": 85} or better
   ```

8. Document new tools or changes in `CLAUDE.md`

## 7 · Adding or Modifying Tests

Place new tests in the appropriate directories:
- `tests/unit/` - For unit tests (fast, no external dependencies)
- `tests/integration/` - For integration tests (database, Redis)
- `tests/e2e/` - For end-to-end tests
- `tests/e2e/voice/` - For voice system tests
- `tests/e2e/webhook/` - For webhook tests

Use pytest markers to categorize tests:
```python
@pytest.mark.unit
def test_something():
    # Test code here
    
@pytest.mark.db
def test_database_feature():
    # Test with database
```

Keep test files under 150 lines of code for maintainability.

## 8 · Host ↔ Container Address Matrix

| Origin | Target | Address to Use |
|--------|--------|----------------|
| Host | MCP server | `host.docker.internal:4244` |
| Host | Flask web | `host.docker.internal:5000` |
| Container | MCP server | `redbarsushi_mcp:4244` |
| Container | Redis | `172.20.0.4:6379` or `redis:6379` |
| Container | PostgreSQL | `172.20.0.3:5432` or `postgres:5432` |

**Important:** Never use `localhost` in host-to-container calls. Always use `host.docker.internal` or the container IP address.

## 9 · Container Management Commands

```bash
# Restart specific containers
docker-compose restart redbarsushi_web redbarsushi_mcp

# View container logs
docker-compose logs -f redbarsushi_web

# Follow logs with filtering
docker-compose logs -f redbarsushi_web | grep ERROR

# Stop all containers
docker-compose down

# Reset everything (will destroy database)
docker-compose down -v
```

## 10 · Autonomous Container Fix Protocol

When encountering container issues, use the autonomous fix tools:

1. First, diagnose the specific issue:
   ```python
   status = call_mcp_tool("container_status", container_name="redbarsushi_web")
   ```

2. For database connection issues:
   ```python
   result = call_mcp_tool("fix_db_connection", container_name="redbarsushi_web", db_host="172.20.0.3")
   ```

3. For Redis connection issues:
   ```python
   result = call_mcp_tool("fix_redis_db", redis_host="172.20.0.4")
   ```

4. For container network issues:
   ```python
   result = call_mcp_tool("fix_network_issues", container_name="redbarsushi_web")
   ```

5. For comprehensive automatic fixing:
   ```python
   result = call_mcp_tool("autonomous_fix_all")
   ```

## 11 · Success Criteria for Autonomous Agents

1. All services report healthy status:
   ```python
   status = call_mcp_tool("container_status")
   # All containers should show "running"
   ```

2. All tests pass with good coverage:
   ```python
   result = call_mcp_tool("run_test", test_type="all", coverage=True)
   # Should show coverage >= 85%
   ```

3. Code quality maintained:
   - No file exceeds 500 lines
   - Tests are under 150 lines each
   - All tools are documented in CLAUDE.md

4. Web and MCP servers respond to health checks:
   ```bash
   curl -sf http://host.docker.internal:4244/health
   curl -sf http://host.docker.internal:5000/healthcheck
   ```

5. Test history documented in `mcp_test_history.md`

---

By following this playbook, autonomous coding agents can effectively debug, validate, and extend the RedBarSushiAI platform while maintaining high quality standards and compatibility with the staging environment.