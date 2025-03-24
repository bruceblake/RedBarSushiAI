#!/usr/bin/env python
"""
Menu validation and fixing utility for RedBarSushiAI

This script provides functionality to validate and repair menu data,
particularly ensuring that prices and PLU values are correctly set.
"""

import json
import os
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('menu_fixer')

def fix_menu_file(file_path):
    """
    Fix issues in the menu file, ensuring prices are correct and PLU values are set.
    
    Args:
        file_path: Path to the menu JSON file
    """
    if not os.path.exists(file_path):
        logger.error(f"Menu file not found at {file_path}")
        return False
        
    logger.info(f"Fixing menu file: {file_path}")
    
    try:
        # Load the current menu data
        with open(file_path, 'r') as f:
            menu_data = json.load(f)
            
        # Process items
        fixed_item_count = 0
        for item in menu_data.get('items', []):
            item_id = item.get('id', 'unknown')
            item_name = item.get('name', 'unknown')
            
            # Fix reference handler if missing
            if not item.get('reference_handler'):
                logger.warning(f"Item {item_name} ({item_id}) is missing reference_handler, fixing...")
                plu = item.get('plu', f"PLU-{item_id}")
                item['reference_handler'] = plu
                fixed_item_count += 1
                
            # Ensure price is a valid number
            if item.get('price', 0) <= 0:
                logger.warning(f"Item {item_name} has zero or negative price: {item.get('price')}, fixing...")
                # Set a default price if needed
                item['price'] = 0.01
                fixed_item_count += 1
                
        # Process modifier groups
        fixed_modifier_group_count = 0
        fixed_modifier_count = 0
        
        for group in menu_data.get('modifierGroups', []):
            group_name = group.get('name', 'unknown')
            
            # Fix missing group ID
            if not group.get('id'):
                # Generate a consistent ID based on name
                import hashlib
                group_id = f"MG-{hashlib.md5(group_name.encode()).hexdigest()[:8]}"
                logger.warning(f"Modifier group '{group_name}' is missing ID, setting to: {group_id}")
                group['id'] = group_id
                fixed_modifier_group_count += 1
            
            # Process modifiers within this group
            for mod in group.get('modifiers', []):
                mod_id = mod.get('id', 'unknown')
                mod_name = mod.get('name', 'unknown')
                
                # Fix missing modifier ID
                if mod_id == 'unknown' or not mod.get('id'):
                    # Generate a consistent ID based on name
                    import hashlib
                    new_mod_id = f"MOD-{hashlib.md5(mod_name.encode()).hexdigest()[:8]}"
                    logger.warning(f"Modifier '{mod_name}' is missing ID, setting to: {new_mod_id}")
                    mod['id'] = new_mod_id
                    mod_id = new_mod_id
                    fixed_modifier_count += 1
                
                # Fix reference handler if missing
                if not mod.get('reference_handler'):
                    logger.warning(f"Modifier {mod_name} in group {group_name} is missing reference_handler, fixing...")
                    plu = mod.get('plu', f"MOD-{mod_id}")
                    mod['reference_handler'] = plu
                    fixed_modifier_count += 1
        
        logger.info(f"Fixed {fixed_item_count} items, {fixed_modifier_group_count} modifier groups, and {fixed_modifier_count} modifiers")
        
        # Write the updated menu back to the file
        with open(file_path, 'w') as f:
            json.dump(menu_data, f, indent=2)
            
        logger.info(f"Updated menu file saved to {file_path}")
        return True
    except Exception as e:
        logger.error(f"Error fixing menu file: {e}")
        return False

def validate_menu_file(file_path):
    """
    Validate the menu file, checking for issues with prices, PLU values, etc.
    
    Args:
        file_path: Path to the menu JSON file
        
    Returns:
        tuple: (is_valid, list of issues)
    """
    if not os.path.exists(file_path):
        return False, [f"Menu file not found: {file_path}"]
        
    try:
        # Load the menu data
        with open(file_path, 'r') as f:
            menu_data = json.load(f)
            
        issues = []
        
        # Check for required top-level fields
        for field in ['items', 'modifiers', 'modifierGroups']:
            if field not in menu_data:
                issues.append(f"Missing required top-level field: {field}")
        
        # Validate items
        for item in menu_data.get('items', []):
            item_name = item.get('name', 'unknown')
            
            # Check for required fields
            if not item.get('name'):
                issues.append(f"Item is missing required 'name' field")
                
            if not item.get('reference_handler'):
                issues.append(f"Item '{item_name}' is missing required 'reference_handler' field")
                
            # Check price
            price = item.get('price')
            if price is None:
                issues.append(f"Item '{item_name}' is missing 'price' field")
            elif price <= 0:
                issues.append(f"Item '{item_name}' has invalid price: {price}")
        
        # Validate modifier groups
        for group in menu_data.get('modifierGroups', []):
            group_name = group.get('name', 'unknown')
            
            # Check for required fields
            if not group.get('name'):
                issues.append(f"Modifier group is missing required 'name' field")
                
            if not group.get('id'):
                issues.append(f"Modifier group '{group_name}' is missing required 'id' field")
                
            # Validate modifiers in this group
            for mod in group.get('modifiers', []):
                mod_name = mod.get('name', 'unknown')
                
                # Check for required fields
                if not mod.get('name'):
                    issues.append(f"Modifier in group '{group_name}' is missing required 'name' field")
                    
                if not mod.get('reference_handler'):
                    issues.append(f"Modifier '{mod_name}' in group '{group_name}' is missing required 'reference_handler' field")
                    
                # Check price
                price = mod.get('price')
                if price is None:
                    issues.append(f"Modifier '{mod_name}' in group '{group_name}' is missing 'price' field")
        
        is_valid = len(issues) == 0
        return is_valid, issues
    except json.JSONDecodeError:
        return False, ["Menu file contains invalid JSON"]
    except Exception as e:
        return False, [f"Error validating menu file: {str(e)}"]

def main():
    """Main entry point for the script."""
    if len(sys.argv) < 2:
        print("Usage: python fix_menu.py <menu_file_path> [--validate-only]")
        return
        
    file_path = sys.argv[1]
    validate_only = "--validate-only" in sys.argv
    
    if validate_only:
        logger.info(f"Validating menu file: {file_path}")
        is_valid, issues = validate_menu_file(file_path)
        
        if is_valid:
            logger.info("Menu file is valid! No issues found.")
        else:
            logger.warning(f"Found {len(issues)} issues in the menu file:")
            for issue in issues:
                logger.warning(f"- {issue}")
    else:
        # Fix the menu file
        if fix_menu_file(file_path):
            # Validate after fixing
            is_valid, issues = validate_menu_file(file_path)
            if is_valid:
                logger.info("Menu file is now valid!")
            else:
                logger.warning(f"Menu file still has {len(issues)} issues:")
                for issue in issues:
                    logger.warning(f"- {issue}")
        else:
            logger.error("Failed to fix menu file.")

if __name__ == "__main__":
    main()