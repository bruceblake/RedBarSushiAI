#!/bin/bash
# Script to standardize requirements files

# Define color codes for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Creating backup of requirements.txt${NC}"
cp requirements.txt requirements.txt.bak

echo -e "${YELLOW}Marking old requirements files as deprecated${NC}"
for req_file in requirements.*.txt; do
  if [ -f "$req_file" ]; then
    echo -e "${YELLOW}Processing $req_file${NC}"
    # Add a deprecated notice at the top of the file
    temp_file=$(mktemp)
    echo "# DEPRECATED: This file is kept for reference only." > "$temp_file"
    echo "# Please use requirements.txt instead." >> "$temp_file"
    echo "# This file will be removed in a future update." >> "$temp_file"
    echo "" >> "$temp_file"
    cat "$req_file" >> "$temp_file"
    mv "$temp_file" "$req_file"
    echo -e "${GREEN}Updated $req_file with deprecation notice${NC}"
  fi
done

echo -e "${GREEN}All requirements files have been updated.${NC}"
echo -e "${YELLOW}Original requirements.txt backed up to requirements.txt.bak${NC}"
echo ""
echo -e "${GREEN}Next steps:${NC}"
echo -e "1. Update workflows to use requirements.txt"
echo -e "2. Update documentation to reference only requirements.txt"
echo -e "3. Remove deprecated files in a future cleanup"