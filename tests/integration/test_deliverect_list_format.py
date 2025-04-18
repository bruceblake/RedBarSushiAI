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


def test_deliverect_list_format(client):
    """Test handling of Deliverect menu in list format."""
    # Create a sample menu in list format with items directly
    sample_menu = [
        # First item - cheeseburger
        {
            "id": "burger1",
            "plu": "CHEESEBURGER",
            "name": "Cheeseburger",
            "price": 1095,  # in cents
            "description": "Juicy beef patty with melted cheese",
            "available": True,
        },
        # Second item - veggie burger
        {
            "id": "burger2",
            "plu": "VEGGIE-BURGER",
            "name": "Veggie Burger",
            "price": 995,  # in cents
            "description": "Plant-based patty with toppings",
            "available": True,
        },
    ]

    # Send request to menu_update endpoint
    response = client.post("/menu_update", json=sample_menu)

    # Check response
    assert response.status_code == 200

    # Now test that we can successfully order these items
    from app.utils.menu_utils import find_menu_item_by_name, load_menu_data

    # Print the menu and name variants for debugging
    menu_data = load_menu_data(force_refresh=True)
    print("\nMENU ITEMS:")
    for item in menu_data.get("items", []):
        print(
            f"  - {item.get('name')} (ID: {item.get('id')}, PLU: {item.get('reference_handler')})"
        )

    print("\nNAME VARIANTS:")
    for variant, name in menu_data.get("name_variants", {}).items():
        print(f"  - '{variant}' -> '{name}'")

    # Try to find the burgers by name and by variants
    print("\nSEARCHING FOR: 'Cheeseburger'")
    cheeseburger = find_menu_item_by_name("Cheeseburger")
    assert cheeseburger is not None
    print(f"FOUND: {cheeseburger.get('name')}")
    assert cheeseburger.get("name") == "Cheeseburger"

    # Test finding by variant (lowercase)
    print("\nSEARCHING FOR: 'cheeseburger'")
    cheeseburger_lower = find_menu_item_by_name("cheeseburger")
    assert cheeseburger_lower is not None
    print(f"FOUND: {cheeseburger_lower.get('name')}")
    assert cheeseburger_lower.get("name") == "Cheeseburger"

    # Test finding by keyword
    print("\nSEARCHING FOR: 'burger'")
    burger_keyword = find_menu_item_by_name("burger")
    assert burger_keyword is not None
    print(f"FOUND: {burger_keyword.get('name')}")
    # The search should find either burger - since both have 'burger' in the name
    assert burger_keyword is not None
    assert any(
        word in burger_keyword.get("name").lower()
        for word in ["burger", "cheeseburger"]
    )

    # Test finding veggie burger
    print("\nSEARCHING FOR: 'Veggie Burger'")
    veggie_burger = find_menu_item_by_name("Veggie Burger")
    assert veggie_burger is not None
    print(f"FOUND: {veggie_burger.get('name')}")
    assert veggie_burger.get("name") == "Veggie Burger"

    # Test finding by using just "veggie"
    print("\nSEARCHING FOR: 'veggie'")
    veggie_keyword = find_menu_item_by_name("veggie")
    assert veggie_keyword is not None
    print(f"FOUND: {veggie_keyword.get('name')}")
    assert veggie_keyword.get("name") == "Veggie Burger"
