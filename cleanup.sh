#!/bin/bash
# Comprehensive cleanup script for RedBarSushiAI project
# This script implements the cleanup plan in CLEANUP_PLAN.md

# Set up error handling
set -e
echo "===== RedBarSushiAI Cleanup Script ====="
echo "This script will clean up and organize the codebase."
echo "It's recommended to have a backup before proceeding."
echo
read -p "Do you want to proceed? (y/n): " confirm
if [ "$confirm" != "y" ]; then
    echo "Cleanup cancelled."
    exit 0
fi

# Create backup
timestamp=$(date +"%Y%m%d_%H%M%S")
backup_dir="../RedBarSushiAI_backup_$timestamp"
echo "Creating backup in $backup_dir..."
mkdir -p "$backup_dir"
cp -r ./* "$backup_dir/"
echo "✅ Backup created successfully"

# Create new directory structure
echo "Creating new directory structure..."
mkdir -p config db/init docker/compose docker/images docs scripts/deployment scripts/maintenance scripts/tools

# Phase 1: Remove unnecessary files
echo "Phase 1: Removing unnecessary files..."

# 1a. Remove all .bak files
find . -name "*.bak" -type f -delete
echo "✅ Removed .bak files"

# 1b. Delete all old logs
rm -f *.log
rm -f mcp_*.log
rm -f e2e_*_test_debug.log
rm -f websocket_*.log
echo "✅ Removed old log files"

# 1c. Delete redundant test environments
rm -rf test_env/ pw_test_env/ e2e_test_env/ websocket_debug_env/
echo "✅ Removed redundant test environments"

# Phase 2: Consolidate MCP-related files
echo "Phase 2: Cleaning up MCP files..."

# Create archive for MCP files if they're needed later
mkdir -p archive/mcp_files
find . -name "mcp_*.py" -exec mv {} archive/mcp_files/ \;
find . -name "fix_mcp_*.sh" -exec mv {} archive/mcp_files/ \;
find . -name "start_mcp_*.sh" -exec mv {} archive/mcp_files/ \;
find . -name "test_mcp_*.py" -exec mv {} archive/mcp_files/ \;
echo "✅ Archived MCP files"

# Phase 3: Organize remaining files
echo "Phase 3: Organizing remaining files..."

# 3a. Organize Docker files
mv docker-compose.yml docker/compose/
mv docker-compose.staging.yml docker/compose/
mv Dockerfile docker/images/
mv docker-entrypoint.sh docker/images/
echo "✅ Organized Docker files"

# 3b. Organize database files
if [ -d "db/init" ]; then
    cp -r db/init db/init
fi
echo "✅ Organized database files"

# 3c. Organize scripts
mv fix_*.sh scripts/maintenance/
mv start_*.sh scripts/deployment/
mv update_*.sh scripts/maintenance/
mv run_*.sh scripts/tools/
echo "✅ Organized scripts"

# 3d. Organize documentation
mv *.md docs/
# Move important docs back to root
cp docs/README.md ./
cp docs/DOCKER_USAGE.md ./
cp docs/CLEANUP_PLAN.md ./
echo "✅ Organized documentation"

# Phase 4: Clean up app directory
echo "Phase 4: Cleaning up app directory..."

# Create directory structure for menu utils consolidation
mkdir -p app/utils/menu
mkdir -p app/utils/database
mkdir -p app/utils/websocket
mkdir -p app/utils/voice

# Main code remains in app directory
echo "✅ Prepared app directory structure"

# Create a .gitignore for logs
echo "Phase 5: Updating .gitignore..."
cat << 'EOF' >> .gitignore

# Added by cleanup script
*.log
logs/
*_backup_*/
.env.*
EOF
echo "✅ Updated .gitignore"

# Create a summary
echo "Phase 6: Creating cleanup summary..."
cat << 'EOF' > CLEANUP_SUMMARY.txt
# RedBarSushiAI Cleanup Summary

Date: $(date)

## Actions Performed
1. Created new directory structure
2. Removed backup files and old logs
3. Archived MCP-related files
4. Organized Docker configuration
5. Organized scripts into categories
6. Organized documentation
7. Updated .gitignore for logs

## Next Steps
1. Consolidate menu utility functions
2. Consolidate stream handlers
3. Create unified database connection module
4. Update imports in all files
5. Test thoroughly

See CLEANUP_PLAN.md for the complete cleanup plan.
EOF
echo "✅ Created cleanup summary"

echo
echo "===== Cleanup complete! ====="
echo "A backup of the original files is in: $backup_dir"
echo "Please review the changes and check CLEANUP_SUMMARY.txt for next steps."
echo
echo "To further clean up the codebase, manual code consolidation is needed:"
echo "1. Consolidate menu utility functions"
echo "2. Consolidate stream handlers"
echo "3. Update imports in affected files"
echo "4. Test the application thoroughly"
echo
echo "Do you want to run the Docker setup with the new structure? (y/n):"
read -p "" run_docker
if [ "$run_docker" == "y" ]; then
    # Copy Docker files back to make them work
    cp docker/compose/docker-compose.yml ./
    ./scripts/deployment/start_docker.sh
fi