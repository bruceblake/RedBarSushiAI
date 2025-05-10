# RedBarSushiAI Codebase Cleanup Plan

This document outlines the comprehensive plan for cleaning up and consolidating the RedBarSushiAI codebase based on the PRD requirements. The plan is organized into distinct phases with specific actions for each component.

## 1. File Deletion and Consolidation

### 1.1 Redundant OpenAI Realtime Client Files

| File | Action | Rationale |
|------|--------|-----------|
| `/app/utils/enhanced_realtime_audio_async.py` | **DELETE** | Redundant implementation with fewer features than the canonical version (`realtime_audio_async.py`). The main implementation already contains robust error handling and logging. |
| `/enhance_openai_client.py` | **DELETE** | One-time script that replaces the canonical client with a simpler version. No longer needed as we're standardizing on the more robust implementation. |

### 1.2 Fixed Model Files Consolidation

| File | Action | Rationale |
|------|--------|-----------|
| `/app/models/menu_fixed.py` | **RENAME** as canonical | This is the corrected version that properly handles JSONB types. The fix_render_deploy.sh script already replaces menu.py with this file. |
| `/app/models/menu.py` | **DELETE** after renaming fixed version | To be replaced by menu_fixed.py (renamed to menu.py). |
| `/app/utils/menu_cache_sdk_fixed.py` | **RENAME** as canonical | This is the version the fix_render_deploy.sh script uses to replace menu_cache_sdk.py. |
| `/app/utils/menu_cache_sdk.py` | **DELETE** after renaming fixed version | To be replaced by menu_cache_sdk_fixed.py (renamed to menu_cache_sdk.py). |

### 1.3 Root Directory Utility Scripts Cleanup

#### One-time Fix Scripts (Delete)

| File | Action | Rationale |
|------|--------|-----------|
| `/fix_api_imports.py` | **DELETE** | One-time fix that should be integrated into fix_render_deploy.sh if still needed. |
| `/fix_config_imports.py` | **DELETE** | One-time fix that should be integrated into fix_render_deploy.sh if still needed. |
| `/fix_db_connection.py` | **DELETE** | One-time database connection fix that's likely no longer needed. |
| `/fix_db_structure.py` | **DELETE** | One-time database structure fix that's likely no longer needed. |
| `/force_debug_logging.py` | **DELETE** | Debug logging should be configured through the main settings. |
| `/force_openai_key.py` | **DELETE** | OpenAI key should be set through environment variables. |
| `/force_reload_agents.py` | **DELETE** | Agent registration should be handled by the AsyncAgentFactory. |

#### Diagnostic Tools (Move to /scripts/diagnostics/)

| File | Action | Rationale |
|------|--------|-----------|
| `/check_env_variables.py` | **MOVE** | Useful diagnostic tool for environment variables. |
| `/check_redis_connection.py` | **MOVE** | Useful for verifying Redis connectivity. |
| `/check_websocket_routes.py` | **MOVE** | Useful for WebSocket route diagnostics. |
| `/debug_websocket.py` | **MOVE** | Useful for WebSocket debugging. |
| `/detect_container.py` | **MOVE** | Useful for container environment detection. |
| `/diagnose.py` | **MOVE** | General diagnostic utility. |
| `/test_env.py` | **MOVE** | Environment testing utility. |
| `/test_openai_connection.py` | **MOVE** | OpenAI connectivity test. |
| `/test_openai_realtime.py` | **MOVE** | OpenAI Realtime API test. |
| `/test_websocket.py` | **MOVE** | WebSocket testing utility. |
| `/verify_docker_env.py` | **MOVE** | Docker environment verification. |
| `/verify_openai_api_key.py` | **MOVE** | OpenAI API key verification. |
| `/verify_websocket_fixes.py` | **MOVE** | WebSocket fixes verification. |
| `/verify_websocket_path.py` | **MOVE** | WebSocket path verification. |
| `/verify_ws_paths.py` | **MOVE** | Related to WebSocket path verification. |
| `/websocket_stability_client.py` | **MOVE** | WebSocket stability testing. |
| `/websocket_test_client.py` | **MOVE** | WebSocket test client. |
| `/websocket_test_server.py` | **MOVE** | WebSocket test server. |

## 2. Code Refactoring for Large Files

### 2.1 Routes Refactoring

#### app/routes/order.py (5672 lines)
**Action**: Split into multiple modules under `app/routes/order/` directory.
**Approach**:
- Separate route handlers by functional areas (already started in the codebase)
- Modules: `checkout.py`, `confirmation.py`, `contact.py`, `modification.py`, `status.py`, `take_order.py`
- Create a common `utils.py` for shared functionality
- Main `order/__init__.py` file should re-export routes from these modules

#### app/routes/realtime.py (2610 lines)
**Action**: Split into multiple modules under `app/routes/realtime/` directory.
**Approach**:
- Separate by functionality: `audio_generator.py`, `stream_handler.py`, `enhanced_stream_handler.py`, `robust_stream_handler.py`
- Create a common connection management module
- Main `realtime/__init__.py` should register all routes from these modules

#### app/routes/menu.py (1699 lines)
**Action**: Split into multiple modules under `app/routes/menu/` directory.
**Approach**:
- Separate routes by operations: `categories.py`, `items.py`, `modifiers.py`, `search.py`, `variants.py`
- Create shared utilities in a `utils.py` file
- Main `menu/__init__.py` should re-export routes

### 2.2 Utils Refactoring

#### app/utils/agent_utils.py (2972 lines)
**Action**: Split into multiple modules under `app/utils/agent_utils/` directory.
**Approach**:
- Create modules: `logging.py`, `menu.py`, `modification.py`, `order.py`, `parsing.py`, `tools.py`
- Main `agent_utils/__init__.py` should re-export all functionality

#### app/utils/agent_orchestration.py (2170 lines)
**Action**: Refactor into smaller components.
**Approach**:
- Extract state-specific logic into separate modules
- Create modules for event handling, agent selection, and tool execution
- Maintain a slim orchestrator class that composes these components

#### app/utils/menu_utils.py (1857 lines)
**Action**: Split by functionality.
**Approach**:
- Create separate modules for different menu operations
- Extract matching logic into a dedicated module
- Separate validation code into its own module

#### app/utils/realtime_audio_async.py (1087 lines)
**Action**: Refactor into smaller components.
**Approach**:
- Extract audio processing utilities into a separate module
- Create dedicated classes for handling different event types
- Extract configuration and session management into separate modules

#### app/utils/fsm_async.py (1137 lines)
**Action**: Split by state handlers.
**Approach**:
- Create a dedicated directory for state handlers
- Group related states in separate modules
- Keep core FSM logic in the main module

### 2.3 API Refactoring

#### app/api/voice_async.py (833 lines)
**Action**: Restructure into smaller modules.
**Approach**:
- Create `app/api/voice/` directory
- Split into modules: `handlers.py` (main WebSocket handler), `audio.py` (audio processing), `silence.py` (VAD handling), `tools.py` (tool execution), `transcript.py` (transcript processing)
- Main module imports and registers the WebSocket handler

### 2.4 Agents Refactoring

#### app/agents/cart_async.py (1023 lines)
**Action**: Split into smaller components.
**Approach**:
- Extract cart management operations into separate modules
- Create utilities for processing different types of cart modifications
- Keep main agent class slim by delegating to these utilities

#### app/agents/frontline_async.py (877 lines)
**Action**: Refactor into smaller components.
**Approach**:
- Extract intent recognition into a separate module
- Create utilities for different conversation phases
- Move complex logic into helper classes

## 3. Fix Render Deploy Script Updates

### 3.1 Direct Script Integration

**Action**: Integrate necessary logic from the fix scripts directly into fix_render_deploy.sh.
**Approach**:
- Extract essential logic from fix_api_imports.py and fix_config_imports.py
- Incorporate this logic directly into fix_render_deploy.sh
- Remove references to these scripts

### 3.2 Agent Registration Simplification

**Action**: Simplify agent registration in fix_render_deploy.sh.
**Approach**:
- Replace the lengthy agent module creation code with a more maintainable approach
- Use a configuration-driven approach to specify required agents
- Ensure agent factory initialization happens in a cleaner way

## 4. Directory Structure Reorganization

### 4.1 Create Scripts Directory

**Action**: Create a structured scripts directory.
**Approach**:
- Create `scripts/` directory with subdirectories:
  - `scripts/diagnostics/` for diagnostic tools
  - `scripts/deployment/` for deployment-related scripts
  - `scripts/maintenance/` for maintenance scripts
  - `scripts/tools/` for development tools
- Move diagnostic scripts to the appropriate directory
- Update documentation to reference new script locations

### 4.2 Restructure Voice-related Components

**Action**: Organize voice-related components into a cohesive structure.
**Approach**:
- Create a consistent structure under `app/api/voice/`
- Move related components from routes to this directory when relevant
- Ensure clean separation of WebSocket handling and business logic

## 5. Implementation Plan

### Phase 1: File Cleanup and Directory Preparation
1. Create scripts directory with subdirectories
2. Rename fixed files to their canonical names
3. Delete redundant OpenAI client files
4. Move diagnostic scripts to their appropriate directories

### Phase 2: Refactoring Large Files
1. Start with the most critical components (voice_async.py, fsm_async.py)
2. Implement directory structures for refactoring
3. Split large files according to the outlined strategies
4. Update imports across the codebase

### Phase 3: Fix Render Deploy Script Updates
1. Extract and integrate logic from fix scripts
2. Simplify agent registration
3. Test deployment process with the updated script

### Phase 4: Validation and Documentation
1. Verify all functionality works after refactoring
2. Update CLAUDE.md to reflect the new codebase structure
3. Create documentation for the scripts directory

## 6. Testing Strategy

After each phase of the cleanup:
1. Run all existing tests
2. Verify basic functionality (menu retrieval, order processing, voice calls)
3. Ensure WebSocket connections work properly
4. Verify Render deployment process

## 7. Success Criteria

1. No redundant or duplicated files remain in the codebase
2. All files are under the 500-line limit where practical
3. Clear, logical directory structure that follows FastAPI best practices
4. Simplified deployment scripts with clear intention
5. No regressions in functionality
6. Updated CLAUDE.md that accurately reflects the refactored codebase