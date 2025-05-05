# Deliverect API Documentation

## Overview

The Deliverect API allows RedBarSushiAI to integrate with restaurant point-of-sale systems for menu management and order processing.

## Base URL

```
https://api.staging.deliverect.com
```

## Key Identifiers

- `channelName`: Scope identifier for API access
- `channelLinkId`: Unique store instance identifier
- `channelOrderId`: Application-generated unique order ID
- `plu`: Product/modifier unique identifier (critical for order processing)

## Endpoints

### Create Order

```
POST /{channelName}/order/{channelLinkId}
```

Places a new order with structured payload containing items identified by PLU.

**Request Body Example**:
```json
{
    "channelOrderId": "RBS-12345-ABCDE",
    "channelOrderDisplayId": "RBS-12345",
    "orderType": 1,
    "pickupTime": "2025-05-03T12:30:00Z",
    "courier": "restaurant",
    "customer": {
        "name": "John Doe",
        "phoneNumber": "+15551234567",
        "email": "john.doe@example.com"
    },
    "orderIsAlreadyPaid": true,
    "payment": {
        "amount": 2550,
        "type": 0
    },
    "note": "No soy sauce please",
    "items": [
        {
            "plu": "CALI-ROLL",
            "name": "California Roll",
            "price": 1200,
            "quantity": 1,
            "subItems": [
                {
                    "plu": "EXTRA-AVO",
                    "name": "Extra Avocado",
                    "price": 150,
                    "quantity": 1
                }
            ]
        },
        {
            "plu": "SPICY-TUNA",
            "name": "Spicy Tuna Roll",
            "price": 1200,
            "quantity": 1
        }
    ],
    "decimalDigits": 2
}
```

**Response**:
- `201 Created`: Order received by Deliverect (valid format)
- `400 Bad Request`: Invalid request format or data
- `401 Unauthorized`: Invalid authentication
- `404 Not Found`: Endpoint not found
- `500 Internal Server Error`: Deliverect server error

### Get Order Status

```
GET /{channelName}/order/{channelLinkId}/{channelOrderId}
```

Retrieves the current status of an order.

**Response Example**:
```json
{
    "orderId": "61e9c9f98e5e2b001c82eabc",
    "status": 20,
    "channelOrderId": "RBS-12345-ABCDE",
    "location": "61e9c9f98e5e2b001c82eabd",
    "channelLink": "61e9c9f98e5e2b001c82eabe"
}
```

## Status Codes

- `10`: Received (initial state)
- `20`: Accepted (confirmed by restaurant)
- `30`: In Preparation
- `40`: Prepared (ready for pickup/delivery)
- `70`: Ready for Pickup
- `80`: Delivered/Completed
- `90`: Rejected (order refused)
- `100`: Cancellation Request
- `110`: Canceled

## Order Types

- `1`: Pick up
- `2`: Delivery
- `3`: Eat-in
- `4`: Curbside

## Payment Types

- `0`: Credit card online
- `1`: Cash
- `2`: Voucher
- `3`: Online payment