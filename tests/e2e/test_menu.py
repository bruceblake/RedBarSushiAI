"""
End-to-end tests for the menu functionality.
"""
import pytest
import time

def test_menu_page_loads(page, base_url):
    """Test that the menu page loads correctly."""
    # Navigate to the menu page
    page.goto(f"{base_url}/menu")
    
    # Verify page title contains expected text
    assert "Menu" in page.title()
    
    # Check for basic page elements
    assert page.locator("h1, h2").count() > 0, "No headings found on menu page"
    
    # Take a screenshot for debugging
    page.screenshot(path="menu-page.png")
    
    print("Menu page loaded successfully")

def test_menu_contains_items(page, base_url):
    """Test that the menu contains items."""
    # Navigate to the menu page
    page.goto(f"{base_url}/menu")
    
    # Wait for menu items to load (adjust selector based on your actual page structure)
    menu_items = page.locator(".menu-item, .item, li, .card").all()
    
    # Check that menu items exist
    assert len(menu_items) > 0, "No menu items found on the page"
    
    # Verify at least one item has expected content
    item_texts = [item.text_content() for item in menu_items]
    print(f"Found menu items: {item_texts[:5]}")
    
    # Look for common menu terms in the items
    common_terms = ["Roll", "Sushi", "Appetizer", "Special", "California"]
    found_terms = []
    for term in common_terms:
        for text in item_texts:
            if term in text:
                found_terms.append(term)
                break
    
    # Check that at least one common term was found
    assert len(found_terms) > 0, f"No common menu terms found. Expected one of: {common_terms}"
    print(f"Found menu terms: {found_terms}")

def test_search_menu(page, base_url):
    """Test the menu search functionality if it exists."""
    # Navigate to the menu page
    page.goto(f"{base_url}/menu")
    
    # Look for a search input
    search_input = page.locator("input[type='search'], input[placeholder*='search'], input[placeholder*='Search']").first
    
    # If search exists, test it
    if search_input.count() > 0:
        # Search for a common item
        search_input.fill("California")
        search_input.press("Enter")
        
        # Wait for search results
        time.sleep(1)
        
        # Check that results contain the search term
        results = page.locator(".menu-item, .item, li, .card").all()
        result_texts = [item.text_content() for item in results]
        
        # Verify at least one result contains "California"
        california_items = [text for text in result_texts if "California" in text]
        assert len(california_items) > 0, "No 'California' items found in search results"
        print(f"Found {len(california_items)} items matching 'California'")
    else:
        print("No search functionality found - skipping search test")
        pytest.skip("No search functionality found on the menu page")

def test_item_details(page, base_url):
    """Test viewing item details if such functionality exists."""
    # Navigate to the menu page
    page.goto(f"{base_url}/menu")
    
    # Find menu items
    menu_items = page.locator(".menu-item, .item, li, .card").all()
    
    if len(menu_items) > 0:
        # Click the first item to see if it shows details
        menu_items[0].click()
        
        # Wait for potential modal or detail page to load
        time.sleep(1)
        
        # Look for common detail elements
        details = page.locator(".item-details, .modal, .details, .description").first
        
        if details.count() > 0:
            # Verify details content
            details_text = details.text_content()
            assert len(details_text) > 0, "Item details are empty"
            print(f"Item details found: {details_text[:100]}...")
        else:
            print("No item details view found - skipping details test")
            pytest.skip("No item details view functionality found")
    else:
        pytest.skip("No menu items found to test details")