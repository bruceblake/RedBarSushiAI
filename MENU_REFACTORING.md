# Menu Routes Refactoring Progress

## Summary

The refactoring of the menu routes is now in progress, with the goal of converting the monolithic app/routes/menu.py (1699 lines) to a modular FastAPI-based structure under app/api/menu/. This follows the successful pattern established during the order routes refactoring.

## What's Been Done

1. **Directory Structure Setup:**
   - Created `app/api/menu/` directory for FastAPI routes
   - Created `app/api/menu/__init__.py` with router registration
   - Updated `app/api/__init__.py` to include the new menu router

2. **Pydantic Models Creation:**
   - Created `app/schemas/menu.py` with comprehensive Pydantic models:
     - Category models (MenuCategoryBase, MenuCategoryResponse, etc.)
     - Item models (MenuItemBase, MenuItemResponse, etc.)
     - Modifier models (MenuModifierBase, MenuModifierResponse, etc.)
     - Variant models (MenuVariantBase, MenuVariantResponse, etc.)
     - Specialized models for operations like snoozing items

3. **Database CRUD Operations:**
   - Created `app/db/crud_menu_async.py` with async CRUD functions:
     - Category operations (get_categories, create_category, etc.)
     - Item operations (get_items, create_item, etc.)
     - Modifier operations (get_modifiers, create_modifier, etc.)
     - Modifier Group operations (get_modifier_groups, create_modifier_group, etc.)
     - Association management operations (add_modifier_to_group, etc.)
     - Special operations like snooze_item and unsnooze_item

4. **Categories Module Implementation:**
   - Created `app/api/menu/categories.py` with FastAPI routes for categories:
     - GET /categories - List all categories
     - GET /categories/{category_id} - Get a specific category
     - POST /categories - Create a new category
     - PUT /categories/{category_id} - Update a category
     - DELETE /categories/{category_id} - Delete a category

5. **Items Module Implementation:**
   - Created `app/api/menu/items.py` with FastAPI routes for items:
     - GET /items - List all items with filtering options
     - GET /items/{item_id} - Get a specific item
     - GET /categories/{category_id}/items - Get items by category
     - POST /items - Create a new item
     - PUT /items/{item_id} - Update an item
     - DELETE /items/{item_id} - Delete an item
     - POST /items/{item_id}/snooze - Snooze/unsnooze an item

6. **Modifiers Module Implementation:**
   - Created `app/api/menu/modifiers.py` with FastAPI routes for modifiers and modifier groups:
     - GET /modifiers - List all modifiers with filtering options
     - GET /modifiers/{modifier_id} - Get a specific modifier
     - POST /modifiers - Create a new modifier
     - PUT /modifiers/{modifier_id} - Update a modifier
     - DELETE /modifiers/{modifier_id} - Delete a modifier
     - POST /modifiers/{modifier_id}/snooze - Snooze/unsnooze a modifier
     - GET /modifier_groups - List all modifier groups with filtering options
     - GET /modifier_groups/{group_id} - Get a specific modifier group
     - POST /modifier_groups - Create a new modifier group
     - PUT /modifier_groups/{group_id} - Update a modifier group
     - DELETE /modifier_groups/{group_id} - Delete a modifier group
     - Association management endpoints:
       - POST /modifier_groups/{group_id}/modifiers/{modifier_id} - Add a modifier to a group
       - DELETE /modifier_groups/{group_id}/modifiers/{modifier_id} - Remove a modifier from a group
       - POST /items/{item_id}/modifier_groups/{group_id} - Add a modifier group to an item
       - DELETE /items/{item_id}/modifier_groups/{group_id} - Remove a modifier group from an item

7. **Variants Module Implementation:**
   - Created `app/api/menu/variants.py` with FastAPI routes for menu name variants:
     - GET /variants - List all variants with filtering options
     - GET /variants/{variant_id} - Get a specific variant by ID
     - GET /variants/phrase/{phrase} - Get a variant by its phrase (case-insensitive)
     - POST /variants - Create a new variant
     - PUT /variants/{variant_id} - Update a variant
     - DELETE /variants/{variant_id} - Delete a variant
     - POST /variants/bulk - Bulk create multiple variants

8. **Search Module Implementation:**
   - Created `app/api/menu/search.py` with FastAPI routes for searching menu entities:
     - GET /search - Search across all menu entities (items, categories, modifiers, variants)
     - GET /search/items - Search menu items specifically
     - GET /search/variants/match - Find a matching variant for a given phrase

## Next Steps

1. **Remaining Module to Implement:**
   - `app/api/menu/update.py` - For handling menu updates from external systems (Deliverect webhook)

2. **Testing the FastAPI Routes:**
   - Create unit tests for each module
   - Add integration tests for the complete menu flow
   - Test Deliverect integration for menu updates

3. **Removing the Original Menu.py File:**
   - Update all imports to use the new modular structure
   - Verify all functionality works with the new FastAPI routes
   - Remove the deprecated `app/routes/menu.py` file

## Approach for Remaining Modules

Each module will follow the same pattern, with:
- A router defined for the specific functionality
- Pydantic models for request/response validation
- Async route handlers with proper error handling
- Database operations through the CRUD layer
- Comprehensive documentation