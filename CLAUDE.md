# Claude Code Helper Documentation

## Menu AI Analysis System

- **AI-Powered Menu Modifier Analysis**: Uses the `OrderParsingAgent` to intelligently link menu items with appropriate modifier groups through the `analyze_menu_item_modifiers()` function in `menu_validator.py`. The AI determines which items need specific modifiers like cooking preferences.

## Integration Points

- The AI-powered menu analysis function is automatically called during menu validation in `validate_and_fix_menu_data()`
- The system dynamically categorizes existing modifier groups (cooking, sides, sauces, etc.) based on their names
- For each menu item without modifiers, the system uses AI to determine appropriate modifier groups
- The existing `check_for_missing_modifiers()` function in `order.py` detects these AI-linked modifiers
- The `OrderParsingAgent` provides intelligent recommendations based on item descriptions and menu structure