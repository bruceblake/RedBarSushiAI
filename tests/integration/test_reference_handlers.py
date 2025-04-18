import pytest
from app import create_app

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


def test_reference_handlers_for_deliverect(client):
    """Test that menu_update endpoint correctly sets reference handlers"""
    # Create a sample menu with categories and products
    sample_menu = {
        "categories": [
            {
                "id": "cat1",
                "name": "Burgers",
                "products": [
                    {
                        "id": "prod1",
                        "name": "Cheeseburger",
                        "price": 1095,  # in cents
                        "plu": "BURG-CHEESE",  # This PLU should be used as reference_handler
                        "description": "Juicy beef patty with melted cheese",
                        "available": True,
                    },
                    {
                        "id": "prod2",
                        "name": "Veggie Burger",
                        "price": 995,  # in cents
                        # No PLU here - should use ID
                        "description": "Plant-based patty with toppings",
                        "available": True,
                    },
                    {
                        # No ID or PLU - should use name-based reference
                        "name": "Kids Burger",
                        "price": 695,  # in cents
                        "description": "Smaller burger for kids",
                        "available": True,
                    },
                ],
            }
        ]
    }

    # Send request to menu_update endpoint
    response = client.post("/menu_update", json=sample_menu)

    # Check response
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True

    # Get the processed menu
    from app.utils.menu_utils import load_menu_data

    menu_data = load_menu_data(force_refresh=True)

    # Print all items for debugging
    print("\nMENU ITEMS WITH REFERENCES:")
    for item in menu_data.get("items", []):
        print(f"  - {item.get('name')} -> {item.get('reference_handler')}")

    # Verify reference handlers
    items = menu_data.get("items", [])

    # Find Cheeseburger and verify its reference handler
    cheeseburger = next(
        (item for item in items if item.get("name") == "Cheeseburger"), None
    )
    assert cheeseburger is not None
    assert cheeseburger.get("reference_handler") == "BURG-CHEESE"

    # Find Veggie Burger and verify its reference handler is the ID
    veggie_burger = next(
        (item for item in items if item.get("name") == "Veggie Burger"), None
    )
    assert veggie_burger is not None
    assert veggie_burger.get("reference_handler") == "prod2"

    # Find Kids Burger and verify it has a name-based reference
    kids_burger = next(
        (item for item in items if item.get("name") == "Kids Burger"), None
    )
    assert kids_burger is not None
    assert kids_burger.get("reference_handler") != ""
    assert "KidsBurger" in kids_burger.get(
        "reference_handler"
    ) or "PROD-" in kids_burger.get("reference_handler")

    # Verify no REF-0000 style references exist
    for item in items:
        assert "REF-" not in item.get("reference_handler", "")
