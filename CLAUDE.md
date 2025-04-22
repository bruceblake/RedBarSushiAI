# Claude Code Helper Documentation

## Menu Structure Validation System

- **Complete Modifier Structure Verification**: The `ensure_complete_modifier_structure()` function in `menu_validator.py` validates and fixes references between menu items, modifier groups, and modifiers to ensure complete structural integrity without any hardcoded assumptions.

## Key Features

1. **Comprehensive ID Validation**: Ensures all items, modifier groups, and modifiers have valid IDs and references
2. **Deliverect Integration Validation**: Verifies PLU/reference_handler fields are properly set for all menu components
3. **Combo Item Support**: Ensures combo/meal deal items are properly linked to appropriate component groups
4. **Invalid Reference Cleanup**: Removes invalid references that would cause order processing failures
5. **Empty Group Handling**: Adjusts minimum requirements for empty modifier groups to prevent ordering errors
6. **Structural Integrity**: Maintains the correct hierarchy of items → modifier groups → modifiers

## Integration Points

- The structure validation is automatically called during menu validation in `validate_and_fix_menu_data()`
- Works with any menu schema or content - no hardcoded assumptions about menu items
- The existing `check_for_missing_modifiers()` function in `order.py` utilizes the validated structure for proper order processing
- Prevents issues with Deliverect order processing by ensuring all reference fields are valid