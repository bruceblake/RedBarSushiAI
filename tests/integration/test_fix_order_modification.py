#!/usr/bin/env python3
"""
Script to fix the order modification bug in the order.py file
"""
import re
import os

def fix_order_modification_bug():
    """Fix the bug in the apply_modifications function"""
    # Path to the order.py file
    order_file_path = "app/routes/order.py"
    
    # Read the current content
    with open(order_file_path, 'r') as f:
        content = f.read()
    
    # Find the apply_modifications function
    apply_mods_pattern = r'def apply_modifications\(current_items, modifications\):.*?return updated_items'
    apply_mods_match = re.search(apply_mods_pattern, content, re.DOTALL)
    
    if not apply_mods_match:
        print("Could not find apply_modifications function")
        return False
    
    # Extract the function
    current_function = apply_mods_match.group(0)
    
    # Create the fixed version - parse string items into dictionaries
    fixed_function = """def apply_modifications(current_items, modifications):
    \"\"\"Apply the specified modifications to the current order\"\"\"
    updated_items = current_items.copy()
    
    # Process removals
    for removal in modifications.get("removals", []):
        # Parse string format like "1x Chicken Burger" into a dict
        if isinstance(removal, str):
            match = re.match(r'(\d+)x\s+(.+)', removal.strip())
            if match:
                qty, name = match.groups()
                removal = {"name": name, "quantity": int(qty)}
            else:
                # If no quantity specified, assume 1
                removal = {"name": removal.strip(), "quantity": 1}
                
        item_name = removal.get("name", "").lower()
        item_qty = removal.get("quantity", 1)
        
        # Try to find matching item by name
        for i, item in enumerate(updated_items):
            if item.get("name", "").lower() == item_name:
                # If quantity to remove matches or exceeds current quantity, remove completely
                if item.get("quantity", 1) <= item_qty:
                    updated_items.pop(i)
                else:
                    # Otherwise just reduce quantity
                    item["quantity"] = item.get("quantity", 1) - item_qty
                break
    
    # Process additions
    for addition in modifications.get("additions", []):
        # Parse string format like "1x Chicken Burger" into a dict
        if isinstance(addition, str):
            match = re.match(r'(\d+)x\s+(.+)', addition.strip())
            if match:
                qty, name = match.groups()
                addition = {"name": name, "quantity": int(qty)}
            else:
                # If no quantity specified, assume 1
                addition = {"name": addition.strip(), "quantity": 1}
        
        # Find the item in the menu to get complete details
        menu_item = find_menu_item_by_name(addition.get("name", ""))
        if not menu_item:
            # Skip if item not found in menu
            continue
            
        # Create a properly formatted item
        new_item = {
            "name": menu_item.get("name", ""),
            "price": menu_item.get("price", 0),
            "reference_handler": menu_item.get("reference_handler", ""),
            "quantity": addition.get("quantity", 1),
            "modifier": addition.get("modifier", [])
        }
        
        # Check if this item already exists in the order
        found = False
        for item in updated_items:
            if item.get("name") == new_item.get("name"):
                # Combine modifiers if they match
                if (not item.get("modifier") and not new_item.get("modifier")) or \
                   str(item.get("modifier")) == str(new_item.get("modifier")):
                    # If the same item with same modifiers, just increase quantity
                    item["quantity"] = item.get("quantity", 1) + new_item.get("quantity", 1)
                    found = True
                    break
                    
        # If not found or modifiers different, add as new item
        if not found:
            updated_items.append(new_item)
    
    return updated_items"""
    
    # Replace the old function with the fixed one
    updated_content = content.replace(current_function, fixed_function)
    
    # Also ensure find_menu_item_by_name is imported
    if "from app.utils.menu_utils import find_menu_item_by_name" not in updated_content:
        # Add import after the existing imports
        import_pattern = r"import.*?\n\n"
        last_import_match = list(re.finditer(import_pattern, updated_content, re.DOTALL))[-1]
        import_end = last_import_match.end()
        
        updated_content = (updated_content[:import_end] + 
                          "from app.utils.menu_utils import find_menu_item_by_name\n\n" + 
                          updated_content[import_end:])
    
    # Write the updated file
    with open(order_file_path, 'w') as f:
        f.write(updated_content)
    
    print(f"Updated {order_file_path} with fixed apply_modifications function")
    return True

if __name__ == "__main__":
    fix_order_modification_bug()