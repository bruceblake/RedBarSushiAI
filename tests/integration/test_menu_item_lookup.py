import pytest
from app import create_app
from app.utils.menu_utils import find_menu_item_by_name

# Mark the entire module as integration tests
pytestmark = pytest.mark.integration


@pytest.fixture
def app():
    # Use in-memory SQLite for these tests
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "SQLALCHEMY_ENGINE_OPTIONS": {"connect_args": {"check_same_thread": False}},
        }
    )

    # Create tables
    with app.app_context():
        from app import db

        db.create_all()

    return app


@pytest.fixture
def client(app):
    return app.test_client()


def test_menu_item_lookup_with_food_keywords(client):
    """Test we can find menu items using food keywords."""
    # First set up test menu data
    menu_data = {
        "items": [
            {
                "id": "cheeseburger",
                "name": "Cheeseburger",
                "price": 10.95,
                "reference_handler": "CHEESEBURGER",
                "available": True,
                "category": "Burgers",
            },
            {
                "id": "veggie_burger",
                "name": "Veggie Burger",
                "price": 9.95,
                "reference_handler": "VEGGIE-BURGER",
                "available": True,
                "category": "Burgers",
            },
            {
                "id": "tuna_roll",
                "name": "Spicy Tuna Roll",
                "price": 12.95,
                "reference_handler": "TUNA-ROLL",
                "available": True,
                "category": "Sushi",
            },
        ],
        "modifiers": [],
        "modifierGroups": [],
        "name_variants": {},  # Will be populated by the system
    }

    # Mock load_menu_data to return our test data
    def mock_load_menu_data(*args, **kwargs):
        # First generate the name variants automatically - process in reverse order
        # to simulate how we process items in real code
        from app.utils.menu_utils import add_name_variants

        # Process items in a specific order to handle name conflicts correctly
        # 1. First direct name variants (exact matches)
        variants = {}
        for item in menu_data["items"]:
            # Add only the direct name first
            name_lower = item["name"].lower()
            variants[name_lower] = item["name"]

        # Then add all other variants
        for item in menu_data["items"]:
            # Create a temporary set of variants for this item
            item_variants = {}
            add_name_variants(item["name"], item_variants)

            # For each variant, check if it's a direct match for this item
            for variant, name in item_variants.items():
                if variant == item["name"].lower():
                    # Direct match - always use this
                    variants[variant] = item["name"]
                # For special food words like "veggie" or "spicy", prefer the item containing that word
                elif variant in item["name"].lower() and len(variant) >= 4:
                    variants[variant] = item["name"]
                elif variant not in variants:
                    # New variant not already in map
                    variants[variant] = item["name"]
        menu_data["name_variants"] = variants
        return menu_data

    # Patch the load_menu_data function
    import unittest.mock

    with unittest.mock.patch(
        "app.utils.menu_utils.load_menu_data", side_effect=mock_load_menu_data
    ):
        # Test finding items by their exact name (case-insensitive)
        cheeseburger = find_menu_item_by_name("Cheeseburger")
        assert cheeseburger is not None
        assert cheeseburger["name"] == "Cheeseburger"

        cheeseburger_lower = find_menu_item_by_name("cheeseburger")
        assert cheeseburger_lower is not None
        assert cheeseburger_lower["name"] == "Cheeseburger"

        # Test finding by general food keyword
        burger = find_menu_item_by_name("burger")
        assert burger is not None
        assert "Burger" in burger["name"]

        # Test finding by specific descriptor
        veggie = find_menu_item_by_name("veggie")
        assert veggie is not None
        assert veggie["name"] == "Veggie Burger"

        # Test finding sushi by name
        tuna = find_menu_item_by_name("Spicy Tuna Roll")
        assert tuna is not None
        assert tuna["name"] == "Spicy Tuna Roll"

        # Test finding sushi by descriptor
        spicy = find_menu_item_by_name("spicy")
        assert spicy is not None
        assert spicy["name"] == "Spicy Tuna Roll"

        # Test finding by partial match
        tuna_roll = find_menu_item_by_name("tuna roll")
        assert tuna_roll is not None
        assert tuna_roll["name"] == "Spicy Tuna Roll"
