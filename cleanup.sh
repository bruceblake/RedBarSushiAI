#!/bin/bash
# Script to clean up unused MCP files

# Set colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}==============================================${NC}"
echo -e "${YELLOW}  RedBarSushiAI - MCP Files Cleanup  ${NC}"
echo -e "${YELLOW}==============================================${NC}"

# Define arrays for different types of files
MCP_SERVER_FILES=(
  "claude_mcp.py"
  "claude_mcp_server.py"
  "enhanced_mcp_server.py"
  "fixed_mcp_server.py"
  "improved_mcp_server.py"
  "mcp_test_runner.py"
  "mcp_test_server.py"
  "minimal_mcp_server.py"
  "python_mcp_server.py"
  "python_mcp_server_fixed.py"
  "simple_mcp_server.py"
  "simple_test_mcp.py"
  "test_claude_mcp.py"
  "test_minimal_mcp.py"
  "test_mcp_connection.py"
)

MCP_SCRIPT_FILES=(
  "connect_mcp.sh.new"
  "echo_mcp.sh"
  "echo_mcp.sh.new"
  "fix_mcp.sh"
  "mcp_fixed.sh"
  "mcp_server.sh"
  "mcp_test_runner.sh"
  "minimal_mcp.sh"
  "reset_mcp.sh"
  "run_enhanced_mcp.sh"
  "run_fixed_mcp.sh"
  "run_improved_mcp.sh"
  "run_mcp_server.sh"
  "run_minimal_mcp.sh"
  "run_python_mcp.sh"
  "run_simple_mcp.sh"
  "setup_mcp.sh"
  "setup_test_mcp.sh"
  "simple_mcp.sh"
  "simple_mcp_server.sh"
  "simple_mcp_server.sh.bak"
  "test_fixed_mcp.sh"
  "test_mcp_connection.sh"
  "use_claude_builtin_mcp.sh"
  "use_claude_mcp.sh"
  "use_enhanced_mcp.sh"
)

MCP_LOG_FILES=(
  "claude_mcp.log"
  "echo_mcp.log"
  "enhanced_mcp.log"
  "fixed_mcp_server.log"
  "improved_mcp.log"
  "mcp_server.log"
  "mcp_test_server.log"
  "minimal_mcp.log"
  "python_mcp.log"
  "simple_mcp_server.log"
  "simple_test_mcp.log"
)

MCP_CONFIG_FILES=(
  ".claude-mcp.json"
  ".mcp.json"
  "mcp_config.json"
)

MCP_DOC_FILES=(
  "MCP_CLAUDE_INTEGRATION.md"
  "MCP_FIXED.md"
  "MCP_INSTRUCTIONS.md"
  "MCP_SOLUTION.md"
  "MCP_TESTING.md"
)

# Function to delete files safely
delete_files() {
  local files=("$@")
  for file in "${files[@]}"; do
    if [ -f "$file" ]; then
      echo -e "${YELLOW}Deleting${NC} $file"
      rm "$file"
      if [ $? -eq 0 ]; then
        echo -e "  ${GREEN}✓ Success${NC}"
      else
        echo -e "  ${RED}✗ Failed${NC}"
      fi
    else
      echo -e "${YELLOW}Skipping${NC} $file (not found)"
    fi
  done
}

# Function to prompt for confirmation
confirm() {
  read -p "$1 (y/n): " response
  case "$response" in
    [yY][eE][sS]|[yY]) 
      true
      ;;
    *)
      false
      ;;
  esac
}

# Kill any running MCP servers
echo -e "${YELLOW}Stopping any running MCP servers...${NC}"
pkill -f "python .*mcp.*py" || true
sleep 1

# Cleanup server files
if confirm "Delete MCP server files?"; then
  echo -e "${YELLOW}Deleting MCP server files...${NC}"
  delete_files "${MCP_SERVER_FILES[@]}"
fi

# Cleanup script files
if confirm "Delete MCP script files?"; then
  echo -e "${YELLOW}Deleting MCP script files...${NC}"
  delete_files "${MCP_SCRIPT_FILES[@]}"
fi

# Cleanup log files
if confirm "Delete MCP log files?"; then
  echo -e "${YELLOW}Deleting MCP log files...${NC}"
  delete_files "${MCP_LOG_FILES[@]}"
fi

# Cleanup config files
if confirm "Delete MCP config files?"; then
  echo -e "${YELLOW}Deleting MCP config files...${NC}"
  delete_files "${MCP_CONFIG_FILES[@]}"
fi

# Cleanup doc files (optional)
if confirm "Delete MCP documentation files? (optional)"; then
  echo -e "${YELLOW}Deleting MCP documentation files...${NC}"
  delete_files "${MCP_DOC_FILES[@]}"
fi

echo -e "${YELLOW}==============================================${NC}"
echo -e "${GREEN}Cleanup completed!${NC}"
echo -e "${YELLOW}Files preserved:${NC}"
echo -e "  - fixed_simple_mcp.py"
echo -e "  - run_fixed_simple_mcp.sh"
echo -e "  - test_staging_e2e.sh"
echo -e "  - test_staging.py"
echo -e "${YELLOW}==============================================${NC}"

# Add a rationale file
cat > FILE_CLEANUP_RATIONALE.md << 'EOF'
# MCP File Cleanup Rationale

## Why These Files Were Removed

During the development of the Model Context Protocol (MCP) integration, multiple experimental implementations were created to address various challenges with the protocol. This resulted in numerous scripts, server implementations, and configuration files.

The cleanup process removed:

1. **Experimental MCP Servers**: Multiple implementations attempted different approaches to solve protocol compatibility issues.

2. **Utility Scripts**: Various scripts to start, register, and test MCP servers.

3. **Log Files**: Debugging logs from development.

4. **Redundant Documentation**: Documentation that has been consolidated into CLAUDE.md.

## Why These Files Were Kept

The following files were preserved as they form the working implementation:

1. **fixed_simple_mcp.py**: The final working MCP server implementation that correctly:
   - Uses protocol version "2024-11-05"
   - Formats tool schemas as "inputSchema" instead of "schema"
   - Returns tool results with the required "content" array structure

2. **run_fixed_simple_mcp.sh**: Script to properly register and start the MCP server.

3. **test_staging_e2e.sh**: Script for running end-to-end tests against the staging environment.

4. **test_staging.py**: Basic testing script for the staging environment.

This streamlined approach ensures the codebase remains focused on the working implementation, making it easier to maintain and understand.
EOF

echo -e "${GREEN}Rationale file created: FILE_CLEANUP_RATIONALE.md${NC}"
echo -e "${YELLOW}==============================================${NC}"