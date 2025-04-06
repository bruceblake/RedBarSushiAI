# Deliverect Async Menu Integration

This document describes the implementation of the Deliverect asynchronous menu update feature.

## Overview

Deliverect's asynchronous menu update flow sends menu data with the following structure:

```json
{
  "body": {
    "menus": [
      {
        "availabilities": [],
        "modifierGroups": {},
        "categories": [
          {
            "id": "cat1",
            "name": "Sushi Rolls",
            "products": [
              {
                "id": "prod1",
                "name": "California Roll",
                "price": 995,
                "plu": "CAL-ROLL",
                "description": "Crab, avocado and cucumber roll",
                "available": true
              }
            ]
          }
        ]
      }
    ],
    "stores": ["store1"],
    "callback": "https://api.staging.deliverect.com/channelName/menuStatus/1234567890"
  }
}
```

The system must process this data and then send a response back to the callback URL with either:
- `{"status": "ONLINE"}` on success
- `{"status": "FAILED", "comment": "Error message"}` on failure

## Implemented Changes

1. Enhanced the `/menu_update` endpoint to handle the asynchronous format:
   - Detection of the async structure with body, menus, stores, and callback
   - Extraction of the first menu from the menus array for processing
   - Implementation of callback responses for success and failure conditions

2. Removed all default menu generation:
   - The system now returns empty menu structures instead of creating default menus when issues occur
   - The `create_default_menu()` function has been removed
   - Empty structure handling for FileNotFoundError cases
   - Empty structure handling for corrupt or invalid menu data

3. Fixed attribute setting on dictionary objects:
   - Changed `menu_data._fixes = []` to use logging instead of setting attributes on dict objects

## Testing

Two tests have been implemented to validate the async menu updates:

1. `test_async_menu_update`: Tests successful processing of a menu with items
2. `test_async_menu_update_no_items`: Tests error handling of a menu with no items

Both tests verify that the callback URL is called with the appropriate status.

## Usage

When Deliverect pushes a menu using the async format, the system will:

1. Detect the async format by checking for the "body" key
2. Extract the callback URL from "body.callback"
3. Extract the store information from "body.stores"
4. Process the first menu from "body.menus"
5. Send the processed menu status to the callback URL

The system will not create any default menus or fallbacks, only processing the data provided in the request.

## Error Handling

The system handles various error conditions:
- No items in menu: Returns 400 error and sends FAILED status to callback
- Processing errors: Sends FAILED status with error details to callback
- File write errors: Sends FAILED status to callback

## Implementation Details

- The async format detection happens in `menu_update()` in `/app/routes/menu.py`
- Callback handling occurs in the same function
- Default menu removal was implemented in `/app/utils/menu_utils.py`
- Tests are available in `test_deliverect_async.py`