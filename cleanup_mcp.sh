#!/bin/bash
# Script to remove MCP server and related files

echo "Removing MCP server directory and related scripts..."

# Remove MCP directory
echo "Removing directory: mcp/"
rm -rf mcp/

# Remove MCP-related scripts
echo "Removing MCP scripts:"
MCP_SCRIPTS=(
  "install-mcp-servers.sh"
  "start_local_mcp.sh"
  "reset_mcp_server.sh"
  "start_proper_mcp.sh"
  "restart_mcp_server.sh"
  "verify_mcp_connection.sh"
  "start_fastmcp.sh"
  "add_mcp_config.sh"
  "cleanup_fastmcp.sh"
  "start_redbarsushi_mcp.sh"
  "restart_mcp_fixed.sh"
  "mcp_ping.sh"
)

for script in "${MCP_SCRIPTS[@]}"; do
  if [ -f "$script" ]; then
    echo "Removing $script"
    rm -f "$script"
  else
    echo "$script not found, skipping"
  fi
done

echo "MCP cleanup completed"