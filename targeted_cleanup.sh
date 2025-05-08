#!/bin/bash
# Targeted cleanup script for RedBarSushiAI
# This script focuses on removing the most confusing and redundant files only

set -e
echo "===== RedBarSushiAI Targeted Cleanup ====="
echo "This script will remove redundant files and organize the codebase"
echo "without major restructuring."
echo

# Create backup 
timestamp=$(date +"%Y%m%d_%H%M%S")
backup_dir="../RedBarSushiAI_backup_$timestamp"
echo "Creating backup in $backup_dir..."
mkdir -p "$backup_dir"
cp -r ./* "$backup_dir/"
echo "✅ Backup created successfully"

# 1. Clean up obvious redundant files
echo "Removing redundant files..."

# Remove all .bak files
find . -name "*.bak" -type f -delete

# Remove log files
rm -f *.log
rm -f e2e_*_test_debug.log
rm -f websocket_*.log
rm -f mcp_*.log

# Create archive directory if it doesn't exist
mkdir -p archive/old_files

# 2. Move MCP-related files to archive
echo "Moving MCP-related files to archive..."
mkdir -p archive/mcp_files

# Move MCP Python files to archive
find . -maxdepth 1 -name "mcp_*.py" -exec mv {} archive/mcp_files/ \;
find . -maxdepth 1 -name "test_mcp_*.py" -exec mv {} archive/mcp_files/ \;

# Move MCP shell scripts to archive
find . -maxdepth 1 -name "fix_mcp_*.sh" -exec mv {} archive/mcp_files/ \;
find . -maxdepth 1 -name "start_mcp_*.sh" -exec mv {} archive/mcp_files/ \;
find . -maxdepth 1 -name "run_mcp_*.sh" -exec mv {} archive/mcp_files/ \;

# 3. Clean up Docker setup
echo "Organizing Docker files..."
mkdir -p docker_config

# Keep only active docker compose file, move others
ls -1 docker-compose*.yml | grep -v "docker-compose.yml" | xargs -I{} mv {} docker_config/

# 4. Move old test environments to archive
echo "Organizing test environments..."
mkdir -p archive/test_envs
find . -maxdepth 1 -type d -name "*_test_env" -exec mv {} archive/test_envs/ \;
find . -maxdepth 1 -type d -name "*_debug_env" -exec mv {} archive/test_envs/ \;

# 5. Create better organization for active files
mkdir -p scripts

# Move utility scripts to scripts directory
echo "Organizing scripts..."
find . -maxdepth 1 -name "check_*.sh" -exec mv {} scripts/ \;
find . -maxdepth 1 -name "fix_*.sh" -not -name "fix_mcp_*.sh" -exec mv {} scripts/ \;
find . -maxdepth 1 -name "update_*.sh" -exec mv {} scripts/ \;

# Create logs directory
mkdir -p logs

# Update .gitignore
echo "Updating .gitignore..."
cat << 'EOF' >> .gitignore

# Added by targeted cleanup
*.log
logs/
*_backup_*/
.env.*
archive/
EOF

# Create a summary of changes
echo "Creating summary of changes..."
cat << EOF > TARGETED_CLEANUP_SUMMARY.md
# RedBarSushiAI Targeted Cleanup Summary

Date: $(date)

## Files Removed
- All *.bak files
- All *.log files
- All debug log files

## Files Archived
- MCP-related Python files (mcp_*.py)
- MCP-related Shell scripts (fix_mcp_*.sh, start_mcp_*.sh)
- Old test environments (*_test_env, *_debug_env)
- Redundant Docker files (extra docker-compose*.yml files)

## Files Organized
- Utility scripts moved to scripts/
- Docker configuration files organized

## New Structure
- archive/ - Contains old files that might be needed for reference
  - mcp_files/ - All MCP-related files
  - old_files/ - Other obsolete files
  - test_envs/ - Old test environments
- docker_config/ - Old Docker configuration files
- logs/ - Directory for log files (added to .gitignore)
- scripts/ - Utility scripts

## Remaining Manual Tasks
1. Consolidate similar files (menu utilities, stream handlers)
2. Clean up imports in affected files
3. Test application functionality
4. Document the new structure

A complete backup of all files exists at: $backup_dir
EOF

echo
echo "===== Targeted cleanup complete! ====="
echo "A backup of the original files is in: $backup_dir"
echo "Please review TARGETED_CLEANUP_SUMMARY.md for details on the changes."
echo
echo "Next steps to consider:"
echo "1. Run Docker environment to verify everything still works"
echo "2. Examine remaining files for additional cleanup"
echo "3. Consider code consolidation for similar modules"