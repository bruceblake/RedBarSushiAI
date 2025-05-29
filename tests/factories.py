"""
Test data factories for quick test data generation.
Uses factory_boy for efficient test data creation.
"""

import factory
from factory import fuzzy, Faker, SubFactory, LazyAttribute
from datetime import datetime, timedelta
import random
from decimal import Decimal

from app.models.menu_async import MenuItem, MenuModifier, MenuModifierGroup, MenuNameVariant
from app.models.order_async import Order, OrderItem, OrderItemModifier
from app.models.location_async import Location


class MenuCategoryFactory(factory.Factory):
    """Factory for menu categories."""
    class Meta:
        model = dict
    
    id = factory.Sequence(lambda n: n)
    name = factory.Faker('random_element', elements=[
        'Sushi Rolls', 'Sashimi', 'Appetizers', 'Beverages', 'Desserts'
    ])
    description = factory.Faker('sentence')
    deliverect_category_id = factory.LazyAttribute(lambda o: f"cat_{o.id}")


class MenuItemFactory(factory.Factory):
    """Factory for menu items."""
    class Meta:
        model = MenuItem
    
    id = factory.Sequence(lambda n: n)
    name = factory.Faker('random_element', elements=[
        'California Roll', 'Spicy Tuna Roll', 'Dragon Roll', 
        'Rainbow Roll', 'Salmon Sashimi', 'Tuna Sashimi',
        'Edamame', 'Miso Soup', 'Gyoza'
    ])
    plu = factory.LazyAttribute(lambda o: f"PLU_{o.name.upper().replace(' ', '_')}_{o.id}")
    price = fuzzy.FuzzyInteger(500, 3000, step=50)  # $5.00 to $30.00
    description = factory.Faker('sentence')
    is_available = fuzzy.FuzzyChoice([True, True, True, False])  # 75% available
    deliverect_item_id = factory.LazyAttribute(lambda o: f"item_{o.id}")
    category_id = fuzzy.FuzzyInteger(1, 5)


class MenuModifierGroupFactory(factory.Factory):
    """Factory for modifier groups."""
    class Meta:
        model = MenuModifierGroup
    
    id = factory.Sequence(lambda n: n)
    name = factory.Faker('random_element', elements=[
        'Spice Level', 'Add-ons', 'Sauce Options', 'Size', 'Preparation'
    ])
    plu = factory.LazyAttribute(lambda o: f"GRP_{o.name.upper().replace(' ', '_')}")
    min_selection = 0
    max_selection = fuzzy.FuzzyChoice([1, 3, 5])
    deliverect_group_id = factory.LazyAttribute(lambda o: f"grp_{o.id}")


class MenuModifierFactory(factory.Factory):
    """Factory for menu modifiers."""
    class Meta:
        model = MenuModifier
    
    id = factory.Sequence(lambda n: n)
    name = factory.Faker('random_element', elements=[
        'Extra Spicy', 'No Spice', 'Extra Avocado', 'No Wasabi',
        'Extra Ginger', 'Light Rice', 'Brown Rice', 'Extra Sauce'
    ])
    plu = factory.LazyAttribute(lambda o: f"MOD_{o.name.upper().replace(' ', '_')}")
    price_change = fuzzy.FuzzyChoice([0, 0, 0, 50, 100, 200])  # Most are free
    is_available = True
    modifier_group_id = fuzzy.FuzzyInteger(1, 5)


class MenuNameVariantFactory(factory.Factory):
    """Factory for menu name variants."""
    class Meta:
        model = MenuNameVariant
    
    id = factory.Sequence(lambda n: n)
    variant_phrase = factory.Faker('word')
    canonical_name = factory.Faker('random_element', elements=[
        'California Roll', 'Spicy Tuna Roll', 'Dragon Roll'
    ])
    target_plu = factory.LazyAttribute(
        lambda o: f"PLU_{o.canonical_name.upper().replace(' ', '_')}"
    )


class OrderFactory(factory.Factory):
    """Factory for orders."""
    class Meta:
        model = Order
    
    id = factory.Sequence(lambda n: n)
    customer_phone = factory.Faker('phone_number')
    customer_name = factory.Faker('name')
    customer_email = factory.Faker('email')
    order_type = fuzzy.FuzzyChoice(['pickup', 'delivery'])
    status = fuzzy.FuzzyChoice(['pending', 'confirmed', 'preparing', 'ready'])
    total_price = fuzzy.FuzzyInteger(1000, 10000)  # $10 to $100
    placed_at = factory.LazyFunction(datetime.utcnow)
    estimated_time = fuzzy.FuzzyInteger(15, 45, step=5)
    deliverect_channel_order_id = factory.LazyAttribute(
        lambda o: f"RBS-{datetime.utcnow().strftime('%Y%m%d')}-{o.id:04d}"
    )


class OrderItemFactory(factory.Factory):
    """Factory for order items."""
    class Meta:
        model = OrderItem
    
    id = factory.Sequence(lambda n: n)
    order_id = factory.LazyAttribute(lambda o: o.order.id if hasattr(o, 'order') else 1)
    menu_item_plu = factory.Faker('random_element', elements=[
        'PLU_CALI_001', 'PLU_SPICY_TUNA_002', 'PLU_DRAGON_003'
    ])
    menu_item_name = factory.LazyAttribute(lambda o: {
        'PLU_CALI_001': 'California Roll',
        'PLU_SPICY_TUNA_002': 'Spicy Tuna Roll',
        'PLU_DRAGON_003': 'Dragon Roll'
    }.get(o.menu_item_plu, 'Unknown Item'))
    quantity = fuzzy.FuzzyInteger(1, 5)
    unit_price = fuzzy.FuzzyInteger(800, 2000)
    total_price = factory.LazyAttribute(lambda o: o.unit_price * o.quantity)


class LocationFactory(factory.Factory):
    """Factory for locations."""
    class Meta:
        model = Location
    
    id = factory.Sequence(lambda n: n)
    name = factory.LazyAttribute(lambda o: f"Red Bar Sushi Location {o.id}")
    address = factory.Faker('address')
    phone = factory.Faker('phone_number')
    deliverect_location_id = factory.LazyAttribute(lambda o: f"loc_{o.id}")
    deliverect_channel_link_id = factory.LazyAttribute(lambda o: f"link_{o.id}")
    business_hours = factory.LazyFunction(lambda: {
        day: {"open": "11:00", "close": "22:00"}
        for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    })


# Composite factories for complex scenarios

class CompleteOrderFactory:
    """Factory for creating complete order with items."""
    
    @staticmethod
    def create(num_items=2, with_modifiers=True):
        order = OrderFactory()
        items = []
        
        for i in range(num_items):
            item = OrderItemFactory(order=order)
            
            if with_modifiers and random.choice([True, False]):
                # Add 1-2 modifiers
                modifiers = []
                for j in range(random.randint(1, 2)):
                    modifier = {
                        "modifier_plu": f"MOD_{j}",
                        "modifier_name": f"Modifier {j}",
                        "price_change": random.choice([0, 50, 100])
                    }
                    modifiers.append(modifier)
                item.modifiers = modifiers
            
            items.append(item)
        
        order.items = items
        order.total_price = sum(item.total_price for item in items)
        
        return order


class ConversationContextFactory:
    """Factory for creating conversation contexts."""
    
    @staticmethod
    def create(state="GREETING", with_cart=False):
        context = {
            "call_sid": f"CA{factory.Faker('uuid4').generate()}",
            "customer_phone": factory.Faker('phone_number').generate(),
            "current_state": state,
            "conversation_start": datetime.utcnow().isoformat(),
            "turns": 0
        }
        
        if state != "GREETING":
            context["customer_name"] = factory.Faker('name').generate()
        
        if with_cart or state in ["ORDERING", "VALIDATION", "CONFIRMATION"]:
            context["cart_items"] = [
                {
                    "name": "California Roll",
                    "plu": "PLU_CALI_001",
                    "quantity": 2,
                    "price": 1295,
                    "modifiers": []
                }
            ]
            context["cart_total"] = 2590
        
        return context


# Batch creation helpers

def create_test_menu(num_items=20, num_modifiers=10):
    """Create a complete test menu."""
    items = MenuItemFactory.create_batch(num_items)
    modifier_groups = MenuModifierGroupFactory.create_batch(5)
    modifiers = MenuModifierFactory.create_batch(num_modifiers)
    
    # Create variants for popular items
    variants = []
    for item in items[:5]:  # First 5 items get variants
        variants.extend([
            MenuNameVariantFactory(
                variant_phrase=item.name.lower().split()[0],
                canonical_name=item.name,
                target_plu=item.plu
            ),
            MenuNameVariantFactory(
                variant_phrase=item.name.lower().replace(' ', ''),
                canonical_name=item.name,
                target_plu=item.plu
            )
        ])
    
    return {
        "items": items,
        "modifier_groups": modifier_groups,
        "modifiers": modifiers,
        "variants": variants
    }