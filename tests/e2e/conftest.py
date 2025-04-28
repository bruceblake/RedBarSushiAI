# tests/conftest.py
import os
import pytest
import json
from playwright.sync_api import APIRequestContext, Playwright

BASE_URL = os.getenv("BASE_URL", "http://localhost:8080")

@pytest.fixture(scope="session")
def api_ctx(playwright: Playwright) -> APIRequestContext:
    """
    One HTTP context for the whole test session, using Playwright's
    built-in 'playwright' fixture to manage the driver lifecycle.
    """
    ctx = playwright.request.new_context(
        base_url=BASE_URL,
        extra_http_headers={"accept": "application/json"},
        timeout=10_000,          # 10 s per request
    )
    yield ctx
    ctx.dispose()

@pytest.fixture
def api_request(api_ctx):
    """
    Wrapper around the Playwright API context that simplifies common operations
    and adds default headers.
    """
    class ApiRequest:
        def post(self, url, data=None, json=None):
            headers = {"Content-Type": "application/json"}
            if data and not json:
                json = data
            return api_ctx.post(url, headers=headers, data=json)
        
        def get(self, url, params=None):
            return api_ctx.get(url, params=params)
    
    return ApiRequest()

@pytest.fixture
def create_test_menu_payload():
    """
    Factory fixture to create test menu payloads with different structures.
    """
    def _create_payload(payload_type="standard", num_items=3, include_modifiers=True):
        """
        Create a test menu payload.
        
        Args:
            payload_type: The type of payload to create ("standard", "async", "direct", "simple")
            num_items: Number of items to include
            include_modifiers: Whether to include modifiers
            
        Returns:
            A dict containing the menu payload
        """
        # Base items that can be included
        items = [
            {
                "id": f"item-{i}",
                "plu": f"PLU-ITEM-{i}",
                "name": f"Test Item {i}",
                "description": f"Description for test item {i}",
                "price": 10.0 + i,
                "available": True,
                "productType": 1
            } for i in range(1, num_items + 1)
        ]
        
        # Modifiers if requested
        modifiers = []
        if include_modifiers:
            modifiers = [
                {
                    "id": f"mod-{i}",
                    "plu": f"PLU-MOD-{i}",
                    "name": f"Test Modifier {i}",
                    "price": 1.0 * i,
                    "available": True,
                    "productType": 2,
                    "parentId": "mod-group-1"
                } for i in range(1, 3)
            ]
        
        # Modifier groups if modifiers are included
        modifier_groups = []
        if include_modifiers:
            modifier_groups = [
                {
                    "id": "mod-group-1",
                    "name": "Test Modifier Group",
                    "min": 0,
                    "max": 2,
                    "multiMax": 1,
                    "productType": 3,
                    "subProducts": [mod["id"] for mod in modifiers]
                }
            ]
        
        if payload_type == "standard":
            # Standard Deliverect format
            return {
                "type": "menu.updated",
                "data": {
                    "menu": {
                        "categories": [
                            {
                                "id": "cat-1",
                                "name": "Test Category",
                                "products": items
                            }
                        ],
                        "modifierGroups": {
                            modifier_groups[0]["id"]: modifier_groups[0]
                        } if include_modifiers else {},
                        "modifiers": {
                            modifier["id"]: modifier for modifier in modifiers
                        } if include_modifiers else {}
                    }
                }
            }
        elif payload_type == "async":
            # Async Deliverect format
            return {
                "body": {
                    "menus": [
                        {
                            "categories": [
                                {
                                    "id": "cat-1",
                                    "name": "Test Category",
                                    "products": items
                                }
                            ],
                            "modifierGroups": {
                                modifier_groups[0]["id"]: modifier_groups[0]
                            } if include_modifiers else {},
                            "modifiers": {
                                modifier["id"]: modifier for modifier in modifiers
                            } if include_modifiers else {}
                        }
                    ],
                    "stores": ["test-channel-link-id"],
                    "callback": "https://api.staging.deliverect.com/testchannel/menuStatus/test123"
                }
            }
        elif payload_type == "direct":
            # Direct format matching our internal structure
            return {
                "items": [
                    {
                        "name": item["name"],
                        "description": item["description"],
                        "price": item["price"],
                        "available": item["available"],
                        "plu": item["plu"],
                        "reference_handler": item["plu"]
                    } for item in items
                ],
                "modifiers": [
                    {
                        "name": modifier["name"],
                        "price": modifier["price"],
                        "available": modifier["available"],
                        "plu": modifier["plu"],
                        "reference_handler": modifier["plu"],
                        "group_id": modifier["parentId"]
                    } for modifier in modifiers
                ] if include_modifiers else [],
                "modifierGroups": [
                    {
                        "id": group["id"],
                        "name": group["name"],
                        "minAllowed": group["min"],
                        "maxAllowed": group["max"],
                        "multiMax": group["multiMax"],
                        "modifiers": [mod["id"] for mod in modifiers]
                    } for group in modifier_groups
                ] if include_modifiers else []
            }
        elif payload_type == "simple":
            # Simple list of items
            return [
                {
                    "name": item["name"],
                    "description": item["description"],
                    "price": item["price"],
                    "available": item["available"],
                    "plu": item["plu"]
                } for item in items
            ]
        else:
            raise ValueError(f"Unknown payload type: {payload_type}")
    
    return _create_payload

@pytest.fixture
def deliverect_menu_payload():
    """
    Create a sample Deliverect menu payload for testing.
    """
    return {
        "id": "test-event-123",
        "type": "menu.updated",
        "timestamp": "2025-04-16T12:00:00Z",
        "data": {
            "account": "test-account",
            "menu": {
                "id": "test-menu-123",
                "name": "Test Menu",
                "version": 1,
                "categories": [
                    {
                        "id": "extras",
                        "name": "Add Extras", 
                        "products": [
                            {
                                "id": "wasabi-extra",
                                "name": "Extra Wasabi",
                                "description": "Additional wasabi on the side",
                                "price": 0.50,
                                "available": True,
                                "productType": 2,
                                "plu": "wasabi-extra"
                            },
                            {
                                "id": "ginger-extra",
                                "name": "Extra Ginger",
                                "description": "Additional ginger on the side",
                                "price": 0.50,
                                "available": True,
                                "productType": 2,
                                "plu": "ginger-extra"
                            }
                        ]
                    },
                    {
                        "id": "appetizers",
                        "name": "Appetizers",
                        "products": [
                            {
                                "id": "edamame",
                                "name": "Edamame",
                                "description": "Steamed soybeans with sea salt",
                                "price": 5.95,
                                "available": True,
                                "plu": "edamame"
                            },
                            {
                                "id": "miso-soup",
                                "name": "Miso Soup",
                                "description": "Traditional Japanese soup with tofu and seaweed",
                                "price": 3.95,
                                "available": True,
                                "plu": "miso-soup"
                            }
                        ]
                    },
                    {
                        "id": "rolls",
                        "name": "Sushi Rolls",
                        "products": [
                            {
                                "id": "cal-roll",
                                "name": "California Roll",
                                "description": "Crab, avocado, and cucumber",
                                "price": 7.95,
                                "available": True,
                                "modifierGroups": ["toppings-group"],
                                "plu": "cal-roll"
                            },
                            {
                                "id": "spicy-tuna",
                                "name": "Spicy Tuna Roll",
                                "description": "Fresh tuna with spicy mayo",
                                "price": 8.95,
                                "available": True,
                                "modifierGroups": ["toppings-group"],
                                "plu": "spicy-tuna"
                            }
                        ]
                    }
                ],
                "modifierGroups": {
                    "toppings-group": {
                        "id": "toppings-group",
                        "name": "Extra Toppings",
                        "min": 0,
                        "max": 5,
                        "multiMax": 2,
                        "productType": 3,
                        "subProducts": ["wasabi-extra", "ginger-extra"]
                    }
                },
                "modifiers": {
                    "wasabi-extra": {
                        "id": "wasabi-extra",
                        "name": "Extra Wasabi",
                        "price": 50,
                        "productType": 2,
                        "parentId": "toppings-group",
                        "plu": "wasabi-extra"
                    },
                    "ginger-extra": {
                        "id": "ginger-extra",
                        "name": "Extra Ginger",
                        "price": 50,
                        "productType": 2,
                        "parentId": "toppings-group",
                        "plu": "ginger-extra"
                    }
                }
            }
        }
    }

@pytest.fixture
def async_menu_payload(deliverect_menu_payload):
    """
    Create an async menu payload based on the standard payload.
    """
    menu = deliverect_menu_payload["data"]["menu"]
    return {
        "body": {
            "menus": [menu],
            "stores": ["test-channel-link-id"],
            "callback": "https://api.staging.deliverect.com/testchannel/menuStatus/test123"
        }
    }
