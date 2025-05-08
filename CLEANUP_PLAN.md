# RedBarSushiAI Comprehensive Cleanup Plan

This document outlines a systematic approach to clean up and organize the codebase.

## 1. Create Organized Directory Structure

```
RedBarSushiAI/
├── app/                # Core application code only
├── config/             # All configuration files
├── db/                 # Database scripts and migrations
├── docker/             # Docker configuration
├── docs/               # Documentation
├── scripts/            # Utility scripts
│   ├── deployment/     # Deployment scripts
│   ├── maintenance/    # Maintenance scripts
│   └── tools/          # Development tools
└── tests/              # All tests organized by type
```

## 2. Cleanup Steps

### Phase 1: Remove Unnecessary Files
- Delete all `.bak` files
- Delete all old logs
- Delete all MCP-related files (per previous request)
- Remove redundant test environments
- Remove duplicate Docker configuration files

### Phase 2: Consolidate Similar Files
- Consolidate menu utility functions
- Consolidate stream handlers
- Consolidate duplicate database connection handling
- Consolidate websocket implementation files

### Phase 3: Reorganize Directory Structure
- Move all deployment scripts to `scripts/deployment/`
- Move all maintenance scripts to `scripts/maintenance/`
- Move all database scripts to `db/`
- Move all Docker files to `docker/`
- Create proper documentation in `docs/`

## 3. Detailed Removal Plan

### Old Logs and Debug Files
- `e2e_*_test_debug.log`
- `mcp_debug.log`
- `mcp_server.log`
- `websocket_*.log`

### Redundant Utilities
- `check_redis_connection.py` → Consolidated to `scripts/maintenance/check_database.py`
- `check_websocket_routes.py` → Consolidated to `scripts/tools/check_routes.py`
- `debug_websocket.py` → Removed, functionality in tests

### Multiple MCP Implementations
- Clean out `mcp/` directory
- Remove all `mcp_*.py` files from root
- Remove all `fix_mcp_*.sh` scripts

### Redundant Docker Files
- Keep only the active `docker-compose.yml`
- Keep only the active `Dockerfile`
- Move all Docker files to `docker/` directory

## 4. Consolidation Plan

### Menu Utilities
- Consolidate `menu_cache.py` and `menu_cache_sdk.py` into `app/utils/menu/cache.py`
- Consolidate `menu_matcher_cache.py` and `menu_matcher_db.py` into `app/utils/menu/matcher.py`
- Consolidate `menu_utils.py` and `menu_utils_db.py` into `app/utils/menu/utils.py`

### Stream Handlers
- Review and consolidate `stream_handler.py`, `enhanced_stream_handler.py`, and `robust_stream_handler.py` 
- Keep only the most robust implementation, renamed to `stream_handler.py`

### Database Connections
- Create a unified database connection module in `app/utils/database.py`
- Ensure all database access goes through this module

## 5. Implementation Order

1. Back up the entire project first
2. Remove redundant files (Phase 1)
3. Create new directory structure
4. Consolidate similar files (Phase 2)
5. Reorganize remaining files (Phase 3)
6. Update imports and references
7. Test the application thoroughly
8. Update documentation

## 6. Expected Outcome

- **Reduced File Count**: Reduce total file count by ~40%
- **Improved Organization**: Clear directory structure with logical grouping
- **Reduced Complexity**: Fewer duplicate implementations
- **Better Maintainability**: Easier to find relevant code
- **Cleaner Repository**: No debug logs or backup files