#!/bin/bash
# Minimal cleanup script for RedBarSushiAI
# This script only removes obviously redundant files without restructuring

set -e
echo "===== RedBarSushiAI File Cleanup ====="
echo "This script will ONLY remove redundant files without changing directory structure."
echo

# Create backup 
timestamp=$(date +"%Y%m%d_%H%M%S")
backup_dir="../RedBarSushiAI_backup_$timestamp"
echo "Creating backup in $backup_dir..."
mkdir -p "$backup_dir"
cp -r ./* "$backup_dir/"
echo "✅ Backup created successfully"

# List files to be removed
echo "The following files will be deleted:"
echo "- All .bak files"
echo "- All log files (*.log)"
echo "- Debug logs (e2e_*_test_debug.log, websocket_*.log, mcp_*.log)"
echo "- Redundant test files and environments"
echo "- MCP debug files"
echo

read -p "Do you want to continue? (y/n): " confirm
if [ "$confirm" != "y" ]; then
    echo "Operation cancelled."
    exit 0
fi

# 1. Remove obviously redundant files
echo "Removing redundant files..."

# Remove all .bak files
find . -name "*.bak" -type f -exec rm -v {} \;

# Remove log files
find . -maxdepth 1 -name "*.log" -exec rm -v {} \;
find . -maxdepth 1 -name "e2e_*_test_debug.log" -exec rm -v {} \;
find . -maxdepth 1 -name "websocket_*.log" -exec rm -v {} \;
find . -maxdepth 1 -name "mcp_*.log" -exec rm -v {} \;

# Remove redundant test environments that are not needed
find . -maxdepth 1 -type d -name "websocket_debug_env" -exec rm -rf {} \;

# Remove duplicate and temporary test files
find . -maxdepth 1 -name "test_failure_modes.py" -exec rm -v {} \;
find . -maxdepth 1 -name "test_imports_only.sh" -exec rm -v {} \;
find . -maxdepth 1 -name "test_refactored_code.sh" -exec rm -v {} \;

# Remove backup MPC files
find . -path "./mcp/archive/*" -name "*.bak" -exec rm -v {} \;

# Create a summary of deleted files
echo "Creating summary of deleted files..."
cat << EOF > CLEANUP_SUMMARY.md
# RedBarSushiAI Redundant Files Cleanup

Date: $(date)

## Files Removed

- All .bak files
- All log files
- Debug logs (e2e_*_test_debug.log, websocket_*.log, mcp_*.log)
- Redundant test environments (websocket_debug_env)
- Duplicate test files (test_failure_modes.py, test_imports_only.sh, test_refactored_code.sh)

## Next Steps

For further cleanup, consider:

1. Running the targeted_cleanup.sh script to organize files without major restructuring
2. Running the full cleanup.sh script for complete codebase reorganization
3. Manually consolidating similar modules (like menu utilities and stream handlers)

A complete backup of all files exists at: $backup_dir
EOF

echo
echo "===== File cleanup complete! ====="
echo "A backup of the original files is in: $backup_dir"
echo "CLEANUP_SUMMARY.md contains details of the changes."
echo
echo "For more comprehensive cleanup, you can run:"
echo "1. ./targeted_cleanup.sh - Organizes files without major restructuring"
echo "2. ./cleanup.sh - Performs complete codebase reorganization"