import pytest
import json
import os

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