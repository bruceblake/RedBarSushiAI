# Deliverect Integration Reference

## Recent Fixes - April 16, 2025

1. **Fixed PLU code format for Deliverect compatibility**:
   - Added automatic cleaning of PLU codes to remove problematic "###PRNT" suffix
   - Updated deliverect.py to sanitize all PLU codes before sending to Deliverect API
   - Fixed the "Invalid PLU" errors in the ordering system

2. **Added support for variant products**:
   - Fixed "Some order product is a variant, but the order does not contain a variation sub item" error
   - Added automatic detection of VAR-PROD prefixed items as variants
   - Added default variation sub-items for variant products with no explicit variations

3. **Enhanced menu update robustness**:
   - Added pre-update backup system to prevent data loss 
   - Improved partial update detection and handling
   - Added automatic menu recovery if update fails

3. **Improved order quantity handling**:
   - Enhanced logging for item quantities to aid in debugging
   - Added better validation and handling of item quantities
   - Ensured consistent quantity handling throughout the ordering process
   - Fixed default quantity (1) when not explicitly specified

This document provides comprehensive documentation for the Deliverect integration in the RedBarSushiAI application, including recent fixes and implementation details for developers.

## Implementation Details

### PLU Code Format Requirements

PLU (Price Look-Up) codes are critical for Deliverect integration. They must follow these requirements:

- Must not contain special characters like `###PRNT`
- The `reference_handler` field should match the `plu` field
- Valid format examples: `P-BURG-CHK`, `RICE-01`, `DRNK-03`
- Invalid format example: `P-BURG-CHK###PRNT` (will be rejected by Deliverect)

Our system now automatically cleans PLU codes before sending them to Deliverect by:
1. Removing the ###PRNT suffix from all PLU codes
2. Ensuring consistency between item names and PLU codes
3. Providing appropriate error messages when PLU issues occur

### Variant Products

Variant products in Deliverect have special requirements:

- Products with PLU codes starting with `VAR-PROD` are considered variants
- All variant products MUST have at least one variation sub-item
- Example: A product with PLU `VAR-PROD-1` must include at least one sub-item

Our system handles variants by:
1. Automatically detecting products with the `VAR-PROD` prefix
2. Adding a default variation sub-item if none is explicitly provided
3. Properly formatting the variation sub-item with the same product PLU plus "-DEFAULT" suffix

### Menu Update Robustness

We've enhanced the menu update process with these improvements:
- Pre-update backup system that preserves existing menu before changes
- Validation of incoming Deliverect data structure before processing
- Partial update detection to prevent accidental menu data loss
- Auto-recovery mechanism if updates fail

### Error Handling Improvements

- Enhanced logging throughout the menu update process
- Auto-recovery mechanisms for failed updates
- Proper validation for empty or invalid menu data

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
      "products": [
        {
          "_id": "67209bfb174a0e5384d4db50",
          "name": "Cheeseburger",
          "plu": "BURG-CHEESE",
          "price": 1095,
          "available": true,
          "description": "Juicy beef patty with melted cheese"
        }
      ]
    }
  ]
}
```

### Order Format

We send orders to Deliverect in this format:

```json
{
  "orderId": "123456789",
  "customer": {
    "name": "John Smith",
    "phone": "+14155552671"
  },
  "items": [
    {
      "name": "Cheeseburger",
      "plu": "BURG-CHEESE",  // We now clean this before sending to remove ###PRNT
      "quantity": 2,         // Can be any positive integer, defaults to 1 if not specified
      "price": 1095,         // Price PER UNIT in cents (not the total for all items)
      "subItems": [
        {
          "name": "extra cheese",
          "plu": "MOD-CHEESE",
          "quantity": 1,     // Modifier quantity can also be specified
          "price": 100       // Price PER UNIT in cents
        }
      ]
    },
    {
      "name": "French Fries",
      "plu": "SIDE-FRIES",
      "quantity": 1,
      "price": 495,
      "subItems": []
    }
  ],
  "total": 2785,            // Total in cents: (1095*2) + 100 + 495
  "status": "NEW",
  "channelOrderId": "123456789",
  "orderType": 1,
  "payment": {
    "amount": 2952,         // Total with tax
    "type": 0
  },
  "taxes": [
    {
      "name": "taxes",
      "total": 167          // Tax amount in cents
    }
  ]
}
```

## Common Issues and Solutions

### Invalid PLU Codes

**Problem**: Orders fail with error "InvalidProduct: Invalid PLU: P-BURG-CHK###PRNT"

**Solution**: 
1. The system now automatically removes "###PRNT" suffix from PLU codes before sending to Deliverect
2. To manually fix, update reference_handler values in menu_data.json to remove any special characters

### Variant Product Errors

**Problem**: Orders fail with error "Some order product (VAR-PROD-1) is a variant, but the order does not contain a variation sub item"

**Solution**:
1. The system now automatically adds a default variation sub-item for products with PLU codes starting with "VAR-PROD"
2. If using custom variants, ensure each variant product has at least one variation sub-item
3. For manual fixes, add a variation to the product in the menu data or change the product's PLU code to a non-variant format

### Menu Updates Failing

**Problem**: Menu updates sometimes fail when receiving partial data from Deliverect

**Solution**:
1. Enhanced menu update process now detects partial updates and merges them with existing data
2. Pre-update backups are created to prevent data loss
3. Auto-recovery restores from backup if an update fails

### Order Quantity Issues

**Problem**: Orders may show incorrect quantities or fail to properly calculate totals

**Solution**:
1. Ensure all order items include a "quantity" field (will default to 1 if omitted)
2. Remember that prices in the API are always PER UNIT and not the total price
3. Use the enhanced logging to verify quantities are being processed correctly
4. For complex orders, verify modifier and child item quantities are correctly set

## Integration Guide

### Steps to Connect with Deliverect

1. Register your location with Deliverect
2. Configure webhook URLs to point to your server
3. Set up API credentials in the application config
4. Ensure all menu items have valid PLU codes:
   - Remove any special characters like ###PRNT from PLU codes
   - Make sure each item has a unique PLU code
   - Keep PLU codes simple (letters, numbers, hyphens only)

### Testing the Integration

1. Use the test endpoints to validate menu updates:
   - `/menu_update` for receiving menu data
   - `/order` for sending test orders

2. Verify PLU codes in the Menu Settings interface

3. Test with common error scenarios:
   - Partial menu updates
   - Network connectivity issues
   - Order modifications