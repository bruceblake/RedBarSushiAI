"""
Tests for handling the complete Deliverect menu format.
These tests verify that all aspects of the Deliverect format are correctly processed.
"""
import pytest
import json
from app.utils.menu_validator import validate_and_fix_menu_data
from app.utils.menu_db_store import menu_db_store
from app.models.menu import MenuItem, MenuModifier, MenuModifierGroup


@pytest.fixture
def deliverect_complex_menu():
    """
    Creates a complex Deliverect menu format including variants, product types, 
    nested modifiers, and other advanced features.
    """
    return {
        "menu": "Complete Test Menu",
        "menuId": "67209bfb174a0e5384d4db61",
        "channelLinkId": "66b35566dc02e27b286fca60", 
        "currency": "USD",
        "menuType": 0,  # DELIVERY_AND_PICKUP
        "nestedModifiers": True,
        "categories": [
            {
                "_id": "67209bfb174a0e5384d4db4f",
                "name": "Main Dishes",
                "description": "Main courses",
                "subProducts": [
                    "67209bfb174a0e5384d4db52"
                ]
            },
            {
                "_id": "67209bfb174a0e5384d4db50",
                "name": "Sides",
                "description": "Side dishes",
                "subProducts": [
                    "67209bfb174a0e5384d4db54",
                    "67209bfb174a0e5384d4db55"
                ]
            }
        ],
        "products": {
            # Regular product
            "67209bfb174a0e5384d4db52": {
                "_id": "67209bfb174a0e5384d4db52",
                "name": "Chicken Tenders",
                "description": "Choose 3, 6 or 9 Pieces of Delicious Fried Chicken",
                "price": 800,  # $8.00
                "plu": "CHKN-TEND",
                "productType": 1,  # 1 = Regular product
                "isVariant": True,  # This is a variant product
                "modifierGroups": ["67209bfb174a0e5384d4db56"],
                "deliveryTax": 9000,
                "takeawayTax": 9000,
                "eatInTax": 9000,
                "isCombo": False,
                "calories": 500,
                "caloriesRangeHigh": 750,
                "nutritionalInfo": {
                    "fat": 20,
                    "sugar": 2,
                    "saturatedFat": 5,
                    "carbohydrates": 30,
                    "protein": 25,
                    "salt": 1,
                    "servingSize": {
                        "amount": 150,
                        "unitType": 1,
                        "countUnitDescription": "g"
                    }
                },
                "productTags": [104, 109]  # Allergens/tags
            },
            # Side dish 1
            "67209bfb174a0e5384d4db54": {
                "_id": "67209bfb174a0e5384d4db54",
                "name": "French Fries",
                "description": "Crispy golden french fries",
                "price": 300,
                "plu": "SIDE-FRIES",
                "productType": 1  # Regular product
            },
            # Side dish 2
            "67209bfb174a0e5384d4db55": {
                "_id": "67209bfb174a0e5384d4db55",
                "name": "Coleslaw",
                "description": "Fresh coleslaw",
                "price": 250,
                "plu": "SIDE-SLAW",
                "productType": 1  # Regular product
            }
        },
        "modifierGroups": {
            # Variant group for chicken tenders
            "67209bfb174a0e5384d4db56": {
                "_id": "67209bfb174a0e5384d4db56",
                "name": "How many pieces?",
                "productType": 3,  # 3 = Modifier group
                "plu": "PIECES-GRP",
                "isVariantGroup": True,  # This is a variant group
                "subProducts": [
                    "67209bfb174a0e5384d4db57",
                    "67209bfb174a0e5384d4db58",
                    "67209bfb174a0e5384d4db59"
                ],
                "min": 1,  # Required selection
                "max": 1,  # Only one size can be selected
                "multiMax": 1  # Can only select each option once
            },
            # Side selection group
            "67209bfb174a0e5384d4db60": {
                "_id": "67209bfb174a0e5384d4db60",
                "name": "Choose your sides",
                "productType": 3,
                "plu": "SIDES-GRP",
                "subProducts": [
                    "67209bfb174a0e5384d4db54",
                    "67209bfb174a0e5384d4db55"
                ],
                "min": 0,  # Optional selection
                "max": 2,  # Can select up to 2 sides
                "multiMax": 1  # Can only select each side once
            }
        },
        "modifiers": {
            # Variant options for chicken tenders
            "67209bfb174a0e5384d4db57": {
                "_id": "67209bfb174a0e5384d4db57",
                "name": "3 Pieces",
                "price": 0,  # Base price already included in product
                "plu": "CHKN-3PC",
                "productType": 2,  # 2 = Modifier
                "parentId": "67209bfb174a0e5384d4db56"
            },
            "67209bfb174a0e5384d4db58": {
                "_id": "67209bfb174a0e5384d4db58",
                "name": "6 Pieces",
                "price": 300,  # $3 extra
                "plu": "CHKN-6PC",
                "productType": 2,
                "parentId": "67209bfb174a0e5384d4db56"
            },
            "67209bfb174a0e5384d4db59": {
                "_id": "67209bfb174a0e5384d4db59",
                "name": "9 Pieces",
                "price": 600,  # $6 extra
                "plu": "CHKN-9PC",
                "productType": 2,
                "parentId": "67209bfb174a0e5384d4db56"
            }
        },
        "supplementalInfo": {
            "ingredients": [
                "Chicken breast",
                "Flour",
                "Spices",
                "Salt"
            ],
            "additives": [
                "E150d - Sulphite ammonia caramel"
            ],
            "fbo": {
                "name": "Test Restaurant GmbH",
                "address": "123 Test St, Test City"
            }
        }
    }


@pytest.fixture
def deliverect_webhook_format(deliverect_complex_menu):
    """
    Creates a Deliverect webhook format (data.menu structure).
    """
    return {
        "type": "menu.updated",
        "data": {
            "account": "test-account",
            "menu": deliverect_complex_menu
        }
    }


@pytest.fixture
def deliverect_variant_order():
    """
    Creates a sample order with variants in Deliverect format.
    """
    return {
        "products": [
            {
                "id": "67209bfb174a0e5384d4db52",  # Chicken Tenders
                "plu": "CHKN-TEND",
                "name": "Chicken Tenders",
                "price": 800,
                "quantity": 1,
                "subProducts": [
                    {
                        "id": "67209bfb174a0e5384d4db58",  # 6 Pieces variant
                        "plu": "CHKN-6PC",
                        "name": "6 Pieces",
                        "price": 300,
                        "quantity": 1
                    }
                ]
            }
        ]
    }


@pytest.mark.integration
def test_validate_deliverect_format(app_with_db, deliverect_complex_menu):
    """
    Test that validate_and_fix_menu_data correctly handles Deliverect format.
    """
    with app_with_db.app_context():
        # First, store some sample menu data in the database to validate against
        menu_db_store.store_menu_data({
            "items": [
                {
                    "name": "Chicken Tenders",
                    "price": 8.00,
                    "plu": "CHKN-TEND",
                    "reference_handler": "CHKN-TEND",
                    "available": True
                },
                {
                    "name": "French Fries",
                    "price": 3.00,
                    "plu": "SIDE-FRIES",
                    "reference_handler": "SIDE-FRIES",
                    "available": True
                }
            ],
            "modifiers": [
                {
                    "name": "3 Pieces",
                    "price": 0,
                    "plu": "CHKN-3PC",
                    "reference_handler": "CHKN-3PC"
                },
                {
                    "name": "6 Pieces",
                    "price": 3.00,
                    "plu": "CHKN-6PC",
                    "reference_handler": "CHKN-6PC"
                }
            ],
            "modifierGroups": [
                {
                    "name": "How many pieces?",
                    "minAllowed": 1,
                    "maxAllowed": 1,
                    "multiMax": 1,
                    "id": "PIECES-GRP"
                }
            ]
        })
        
        # Validate the complex Deliverect menu
        validated_menu = validate_and_fix_menu_data(deliverect_complex_menu)
        
        # Verify items were correctly processed
        assert "items" in validated_menu
        assert len(validated_menu["items"]) >= 1
        
        # Verify item properties including variants
        chicken_tenders = next((item for item in validated_menu["items"] 
                              if item.get("plu") == "CHKN-TEND"), None)
        assert chicken_tenders is not None
        assert chicken_tenders.get("isVariant") is True
        assert "price" in chicken_tenders
        assert chicken_tenders.get("reference_handler") == "CHKN-TEND"
        
        # Verify modifiers and variant group
        assert "modifiers" in validated_menu
        assert "modifierGroups" in validated_menu
        
        # Find the variant group
        variant_group = next((group for group in validated_menu["modifierGroups"] 
                            if group.get("isVariantGroup") is True), None)
        assert variant_group is not None
        assert variant_group.get("minAllowed") == 1
        assert variant_group.get("maxAllowed") == 1
        
        # Find modifiers
        pieces_6 = next((mod for mod in validated_menu["modifiers"] 
                       if mod.get("plu") == "CHKN-6PC"), None)
        assert pieces_6 is not None
        assert pieces_6.get("price") == 300  # $3.00 in cents


@pytest.mark.integration
def test_validate_webhook_format(app_with_db, deliverect_webhook_format):
    """
    Test that validate_and_fix_menu_data correctly handles Deliverect webhook format.
    """
    with app_with_db.app_context():
        # First, store some sample menu data in the database to validate against
        menu_db_store.store_menu_data({
            "items": [
                {
                    "name": "Chicken Tenders",
                    "price": 8.00,
                    "plu": "CHKN-TEND",
                    "reference_handler": "CHKN-TEND",
                    "available": True
                }
            ]
        })
        
        # Validate the webhook format
        validated_menu = validate_and_fix_menu_data(deliverect_webhook_format)
        
        # Verify items were correctly extracted from the webhook format
        assert "items" in validated_menu
        assert len(validated_menu["items"]) >= 1
        
        # Verify a specific item
        chicken_tenders = next((item for item in validated_menu["items"] 
                              if item.get("plu") == "CHKN-TEND"), None)
        assert chicken_tenders is not None


@pytest.mark.integration
def test_nested_modifiers(app_with_db, deliverect_complex_menu):
    """
    Test handling of nested modifiers in Deliverect format.
    """
    with app_with_db.app_context():
        # First, store some sample menu data in the database to validate against
        menu_db_store.store_menu_data({
            "items": [
                {
                    "name": "Chicken Tenders",
                    "price": 8.00,
                    "plu": "CHKN-TEND",
                    "reference_handler": "CHKN-TEND",
                    "available": True
                }
            ],
            "modifiers": [
                {
                    "name": "3 Pieces",
                    "price": 0,
                    "plu": "CHKN-3PC",
                    "reference_handler": "CHKN-3PC"
                }
            ],
            "modifierGroups": [
                {
                    "name": "How many pieces?",
                    "minAllowed": 1,
                    "maxAllowed": 1,
                    "multiMax": 1,
                    "id": "PIECES-GRP"
                }
            ]
        })
        
        # Add nested modifiers to the menu
        deliverect_complex_menu["modifierGroups"]["67209bfb174a0e5384d4db56"]["subProducts"].append("67209bfb174a0e5384d4db60")
        
        # Validate the menu with nested modifiers
        validated_menu = validate_and_fix_menu_data(deliverect_complex_menu)
        
        # Verify the nested structure was processed correctly
        assert "modifierGroups" in validated_menu
        
        # Find the parent group
        parent_group = next((group for group in validated_menu["modifierGroups"] 
                           if group.get("plu") == "PIECES-GRP"), None)
        assert parent_group is not None
        
        # Check that modifiers list includes both direct modifiers and nested group
        modifiers_list = parent_group.get("modifiers", [])
        assert len(modifiers_list) >= 3  # Should have at least 3 items


@pytest.mark.integration
def test_nutritional_info(app_with_db, deliverect_complex_menu):
    """
    Test handling of nutritional information in Deliverect format.
    """
    with app_with_db.app_context():
        # First, store some sample menu data in the database to validate against
        menu_db_store.store_menu_data({
            "items": [
                {
                    "name": "Chicken Tenders",
                    "price": 8.00,
                    "plu": "CHKN-TEND",
                    "reference_handler": "CHKN-TEND",
                    "available": True
                }
            ]
        })
        
        # Validate the menu with nutritional info
        validated_menu = validate_and_fix_menu_data(deliverect_complex_menu)
        
        # Verify nutritional info was preserved
        chicken_tenders = next((item for item in validated_menu["items"] 
                              if item.get("plu") == "CHKN-TEND"), None)
        assert chicken_tenders is not None
        assert "nutritionalInfo" in chicken_tenders
        assert "calories" in chicken_tenders
        assert chicken_tenders["calories"] == 500
        
        # Verify serving size info was preserved
        assert "servingSize" in chicken_tenders["nutritionalInfo"]
        assert chicken_tenders["nutritionalInfo"]["servingSize"]["amount"] == 150
        
        # Verify allergens/tags
        assert "productTags" in chicken_tenders
        assert 104 in chicken_tenders["productTags"]
        assert 109 in chicken_tenders["productTags"]


@pytest.mark.integration
def test_supplemental_info(app_with_db, deliverect_complex_menu):
    """
    Test handling of supplemental information in Deliverect format.
    """
    with app_with_db.app_context():
        # First, store some sample menu data in the database to validate against
        menu_db_store.store_menu_data({
            "items": [
                {
                    "name": "Chicken Tenders",
                    "price": 8.00,
                    "plu": "CHKN-TEND",
                    "reference_handler": "CHKN-TEND",
                    "available": True
                }
            ]
        })
        
        # Validate the menu with supplemental info
        validated_menu = validate_and_fix_menu_data(deliverect_complex_menu)
        
        # Verify supplemental info was preserved
        assert "supplementalInfo" in validated_menu
        assert "ingredients" in validated_menu["supplementalInfo"]
        assert "Chicken breast" in validated_menu["supplementalInfo"]["ingredients"]
        
        # Verify additives
        assert "additives" in validated_menu["supplementalInfo"]
        assert len(validated_menu["supplementalInfo"]["additives"]) > 0
        
        # Verify FBO info
        assert "fbo" in validated_menu["supplementalInfo"]
        assert validated_menu["supplementalInfo"]["fbo"]["name"] == "Test Restaurant GmbH"