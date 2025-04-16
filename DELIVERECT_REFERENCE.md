# Deliverect Integration Reference Guide

This document provides comprehensive documentation for the Deliverect integration in the RedBarSushiAI application, including recent fixes and implementation details for developers.

## Recent Fixes - April 16, 2025

We've implemented several important fixes to enhance the reliability of the Deliverect integration:

1. **Fixed import errors in menu processing**:
   - Added proper import statements in menu.py and menu_utils.py
   - Fixed scoping issues with os and json modules
   - Ensured atomic file operations when writing menu data

2. **Enhanced menu update robustness**:
   - Added pre-update backup system
   - Added validation of incoming Deliverect data
   - Improved partial update detection and handling
   - Fixed PLU code formatting for items sent to Deliverect (removed ###PRNT suffix)

3. **Improved error handling**:
   - Added better logging throughout menu update process
   - Added auto-recovery mechanisms for failed updates
   - Added proper validation for empty or invalid menu data

These improvements ensure the menu update endpoint properly processes Deliverect data while maintaining data integrity.

## Deliverect API Structure

### Menu Data Format

Deliverect sends menu data in the following structures:

```json
{
  "availabilities": [...],
  "bundles": {},
  "categories": [
    {
      "_id": "67209bfb174a0e5384d4db4f",
      "name": "Steak & Burgers",
      "posCategoryId": "STK",
      "products": ["6721daafc33216a11b4e239d", "6721daafc33216a11b4e23a2", "66b35629a7eb47d479f1d31b"]
    }
  ],
  "modifierGroups": {
    "67209bb4174a0e5384d4d9fb": {
      "_id": "67209bb4174a0e5384d4d9fb",
      "name": "Ingredients",
      "max": 4,
      "min": 0,
      "plu": "INGRD",
      "subProducts": ["67209bb4174a0e5384d4d9fd", "67209bb4174a0e5384d4d9ff"]
    }
  },
  "modifiers": {
    "67209bb4174a0e5384d4d9fd": {
      "_id": "67209bb4174a0e5384d4d9fd",
      "name": "Tomatoes",
      "price": 0,
      "plu": "TOMAT"
    }
  },
  "products": {
    "6721daafc33216a11b4e239d": {
      "_id": "6721daafc33216a11b4e239d",
      "name": "Deluxe Burger",
      "price": 1100,
      "plu": "P-BRGR-1",
      "description": "Combo and Nested Modifiers structure"
    }
  }
}
```

### Menu Data Processing Flow

1. **Receipt**: Data arrives at `/menu_update` endpoint from Deliverect
2. **Format Detection**: System identifies the type of data (standard, list, async)
3. **Processing**: Data goes through `process_deliverect_menu()` to convert to internal format
4. **Validation**: Data is validated through `validate_and_fix_menu_data()`
5. **PLU Verification**: System ensures all items have valid PLU codes
6. **Partial Update Handling**: For partial updates, data is merged with existing menu
7. **Name Variant Generation**: System generates variants for voice recognition
8. **Storage**: Data is written to disk with atomic file operations
9. **Callback**: If provided, status is sent back to Deliverect

## PLU Format Requirements

PLU (Price Look-Up) codes are critical for Deliverect integration. Requirements:

- Must not contain special characters like `###PRNT`
- The `reference_handler` field should match the `plu` field
- Valid format example: `P-BURG-CHK`, `RICE-01`, `DRNK-03`
- Invalid format example: `P-BURG-CHK###PRNT` (will be rejected by Deliverect)

## Internal Data Structure

Our system processes Deliverect data into this format:

```json
{
  "items": [
    {
      "name": "Chicken Burger",
      "reference_handler": "P-BURG-CHK",
      "plu": "P-BURG-CHK",
      "price": 6.95,
      "description": "Delicious chicken burger",
      "category": "Burgers",
      "id": "ITEM-CHICKEN",
      "available": true,
      "snoozed": false
    }
  ],
  "modifiers": [],
  "modifierGroups": [],
  "name_variants": {
    "chicken burger": "Chicken Burger",
    "chicken": "Chicken Burger"
  }
}
```

## Error Handling and Recovery

The menu update process includes several safeguards:

1. **Pre-Update Backup**: Before processing, a backup of the current menu is created
2. **Data Validation**: JSON parsing with multiple fallback methods
3. **PLU Validation**: System checks for valid PLU codes and logs warnings
4. **Partial Update Detection**: System detects and properly handles partial menu updates
5. **Atomic File Writing**: Uses a temporary file and atomic move to prevent corruption
6. **Auto-Recovery**: If menu becomes empty after update, system can restore from backup

## Test Cases

We maintain several test suites for the Deliverect integration:

- `test_deliverect.py`: Basic API functionality tests
- `test_deliverect_deep_scan.py`: Tests for handling nested data structures
- `test_deliverect_list_format.py`: Tests for simple list-formatted menu data
- `test_deliverect_async.py`: Tests for async menu updates with callbacks
- `test_menu_import.py`: Tests for menu import functionality
- `test_menu_variant_matching.py`: Tests for name variant generation

## Sample Deliverect Menu Structure

The Deliverect menu can be very complex. Here's an example of a simple menu:

```json
[
  {
    "availabilities": [
      {
        "dayOfWeek": 1,
        "endTime": "23:59",
        "startTime": "00:00"
      }
    ],
    "categories": [
      {
        "_id": "67209bfb174a0e5384d4db4f",
        "name": "Steak & Burgers",
        "products": [
          "6721daafc33216a11b4e239d",
          "6721daafc33216a11b4e23a2"
        ]
      }
    ],
    "products": {
      "6721daafc33216a11b4e239d": {
        "_id": "6721daafc33216a11b4e239d",
        "name": "Deluxe Burger",
        "price": 1100,
        "plu": "P-BRGR-1",
        "description": "Delicious burger"
      }
    }
  }
]
```

## Environment Variables

Important environment variables for Deliverect integration:

- `DELIVERECT_CLIENT_ID`: API client ID for authentication
- `DELIVERECT_CLIENT_SECRET`: API client secret for authentication
- `BASE_URL`: Base URL for webhook callbacks
- `MENU_FILE_PATH`: Optional custom path for the menu data file

## Troubleshooting Common Issues

1. **Empty menu after update**: 
   - Check if it was a partial update
   - Check logs for validation errors
   - Ensure PLU formats are correct

2. **Orders being rejected by Deliverect**:
   - Verify PLU formats don't contain special characters
   - Ensure reference_handler matches plu field
   - Check that all modifiers have valid PLUs

3. **Items not found in voice orders**:
   - Check if name_variants are being generated
   - Verify the item wasn't snoozed
   - Check for category/availability issues

## Best Practices

1. Always ensure PLU codes match between reference_handler and plu fields
2. Remove any special characters like ###PRNT from PLU codes
3. Test partial menu updates carefully to ensure they don't overwrite the full menu
4. Maintain good name_variants for voice recognition
5. Use proper error handling when interacting with Deliverect API

## References

- [Official Deliverect API Documentation](https://api-docs.deliverect.com/)
- [Menu Webhooks Guide](https://docs.deliverect.com/reference/menu-webhooks)
- [Order Management Guide](https://docs.deliverect.com/reference/order-management)