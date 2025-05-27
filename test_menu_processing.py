#!/usr/bin/env python
"""Test the menu processing implementation."""

import json
from app.utils.deliverect.menu import process_deliverect_menu

# Test with the sample menu
with open("sample_deliverect_menu_subset.json", "r") as f:
    sample_menu = json.load(f)

# Process the menu
result = process_deliverect_menu(sample_menu)

# Print results
print("Processed Menu Results:")
print(f"Items: {len(result['items'])}")
for item in result['items']:
    print(f"  - {item['name']} (PLU: {item['plu']}, Price: ${item['price']})")

print(f"\nModifier Groups: {len(result['modifierGroups'])}")
for group in result['modifierGroups']:
    print(f"  - {group['name']} (min: {group['min_selection']}, max: {group['max_selection']})")
    for mod in group.get('modifiers', []):
        print(f"    - {mod['name']} (${mod['price_change']})")

print(f"\nModifiers: {len(result['modifiers'])}")
for modifier in result['modifiers']:
    print(f"  - {modifier['name']} (PLU: {modifier['plu']}, Price Change: ${modifier['price_change']})")

print(f"\nItem-Modifier Group Relationships: {len(result.get('item_modifier_groups', []))}")
for rel in result.get('item_modifier_groups', []):
    print(f"  - Item {rel['item_plu']} -> Group {rel['modifier_group_name']}")

print(f"\nName Variants: {len(result['name_variants'])}")
for variant, plu in list(result['name_variants'].items())[:5]:
    print(f"  - '{variant}' -> {plu}")