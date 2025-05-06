-- Insert sample menu categories
INSERT INTO menu_categories (name, description) VALUES
('Sushi Rolls', 'Fresh and delicious sushi rolls'),
('Sashimi', 'Premium cuts of raw fish'),
('Appetizers', 'Starters to begin your meal')
ON CONFLICT DO NOTHING;

-- Insert sample menu items
INSERT INTO menu_items (category_id, name, description, price, plu) VALUES
(1, 'California Roll', 'Crab, avocado, cucumber', 1200, 'CALI-ROLL'),
(1, 'Spicy Tuna Roll', 'Fresh tuna with spicy sauce', 1300, 'SPICY-TUNA'),
(1, 'Dragon Roll', 'Eel, avocado, cucumber', 1500, 'DRAGON-ROLL'),
(1, 'Rainbow Roll', 'California roll topped with assorted sashimi', 1600, 'RAINBOW-ROLL'),
(2, 'Salmon Sashimi', 'Fresh cuts of salmon', 1500, 'SALMON-SASH'),
(2, 'Tuna Sashimi', 'Premium cuts of tuna', 1700, 'TUNA-SASH'),
(2, 'Yellowtail Sashimi', 'Slices of yellowtail', 1600, 'YTAIL-SASH'),
(3, 'Edamame', 'Steamed soybeans with sea salt', 600, 'EDAMAME'),
(3, 'Miso Soup', 'Traditional Japanese soup with tofu and seaweed', 500, 'MISO-SOUP'),
(3, 'Gyoza', 'Pan-fried pork dumplings', 800, 'GYOZA')
ON CONFLICT DO NOTHING;

-- Insert sample modifier groups
INSERT INTO menu_modifier_groups (name, min_selection, max_selection, multi_max, is_variant_group) VALUES
('Spice Level', 0, 1, 1, FALSE),
('Additional Toppings', 0, 3, 1, FALSE),
('Size Options', 1, 1, 1, TRUE)
ON CONFLICT DO NOTHING;

-- Get the IDs for the inserted modifier groups
DO $$
DECLARE
    spice_group_id INTEGER;
    toppings_group_id INTEGER;
    size_group_id INTEGER;
BEGIN
    SELECT id INTO spice_group_id FROM menu_modifier_groups WHERE name = 'Spice Level';
    SELECT id INTO toppings_group_id FROM menu_modifier_groups WHERE name = 'Additional Toppings';
    SELECT id INTO size_group_id FROM menu_modifier_groups WHERE name = 'Size Options';

    -- Insert modifiers for Spice Level
    INSERT INTO menu_modifiers (modifier_group_id, name, price_change, plu) VALUES
    (spice_group_id, 'Mild', 0, 'SPICE-MILD'),
    (spice_group_id, 'Medium', 0, 'SPICE-MED'),
    (spice_group_id, 'Hot', 0, 'SPICE-HOT'),
    (spice_group_id, 'Extra Hot', 100, 'SPICE-XHOT')
    ON CONFLICT DO NOTHING;

    -- Insert modifiers for Additional Toppings
    INSERT INTO menu_modifiers (modifier_group_id, name, price_change, plu) VALUES
    (toppings_group_id, 'Extra Avocado', 150, 'EXTRA-AVO'),
    (toppings_group_id, 'Extra Fish', 200, 'EXTRA-FISH'),
    (toppings_group_id, 'Masago', 100, 'TOP-MASAGO'),
    (toppings_group_id, 'Tempura Flakes', 100, 'TOP-TEMPURA')
    ON CONFLICT DO NOTHING;

    -- Insert modifiers for Size Options
    INSERT INTO menu_modifiers (modifier_group_id, name, price_change, plu) VALUES
    (size_group_id, 'Regular', 0, 'SIZE-REG'),
    (size_group_id, 'Large', 300, 'SIZE-LRG')
    ON CONFLICT DO NOTHING;

    -- Associate modifier groups with menu items
    -- Spice Level for Spicy Tuna Roll
    INSERT INTO item_modifier_groups (menu_item_id, modifier_group_id)
    SELECT m.id, spice_group_id
    FROM menu_items m
    WHERE m.plu = 'SPICY-TUNA'
    ON CONFLICT DO NOTHING;

    -- Additional Toppings for California Roll
    INSERT INTO item_modifier_groups (menu_item_id, modifier_group_id)
    SELECT m.id, toppings_group_id
    FROM menu_items m
    WHERE m.plu = 'CALI-ROLL'
    ON CONFLICT DO NOTHING;

    -- Additional Toppings for Spicy Tuna Roll
    INSERT INTO item_modifier_groups (menu_item_id, modifier_group_id)
    SELECT m.id, toppings_group_id
    FROM menu_items m
    WHERE m.plu = 'SPICY-TUNA'
    ON CONFLICT DO NOTHING;

    -- Size Options for Miso Soup
    INSERT INTO item_modifier_groups (menu_item_id, modifier_group_id)
    SELECT m.id, size_group_id
    FROM menu_items m
    WHERE m.plu = 'MISO-SOUP'
    ON CONFLICT DO NOTHING;
END $$;

-- Insert menu name variants
INSERT INTO menu_name_variants (variant_phrase, canonical_name, target_plu) VALUES
('california', 'California Roll', 'CALI-ROLL'),
('cali roll', 'California Roll', 'CALI-ROLL'),
('crab avocado roll', 'California Roll', 'CALI-ROLL'),
('spicy tuna', 'Spicy Tuna Roll', 'SPICY-TUNA'),
('hot tuna roll', 'Spicy Tuna Roll', 'SPICY-TUNA'),
('dragon', 'Dragon Roll', 'DRAGON-ROLL'),
('eel avocado', 'Dragon Roll', 'DRAGON-ROLL'),
('rainbow', 'Rainbow Roll', 'RAINBOW-ROLL'),
('salmon sashimi', 'Salmon Sashimi', 'SALMON-SASH'),
('salmon', 'Salmon Sashimi', 'SALMON-SASH'),
('tuna sashimi', 'Tuna Sashimi', 'TUNA-SASH'),
('tuna', 'Tuna Sashimi', 'TUNA-SASH'),
('yellowtail', 'Yellowtail Sashimi', 'YTAIL-SASH'),
('hamachi', 'Yellowtail Sashimi', 'YTAIL-SASH'),
('edamame', 'Edamame', 'EDAMAME'),
('soybeans', 'Edamame', 'EDAMAME'),
('miso', 'Miso Soup', 'MISO-SOUP'),
('miso soup', 'Miso Soup', 'MISO-SOUP'),
('gyoza', 'Gyoza', 'GYOZA'),
('dumplings', 'Gyoza', 'GYOZA'),
('potstickers', 'Gyoza', 'GYOZA')
ON CONFLICT DO NOTHING;

-- Insert sample locations
INSERT INTO locations (name, deliverect_channel_link_id, address, phone, email) VALUES
('Red Bar Sushi Downtown', 'channel_link_downtown', '123 Main St, City, ST 12345', '555-123-4567', 'downtown@redbarsushi.com'),
('Red Bar Sushi Uptown', 'channel_link_uptown', '456 Park Ave, City, ST 12345', '555-765-4321', 'uptown@redbarsushi.com')
ON CONFLICT DO NOTHING;

-- Insert sample order for testing (with a completed status)
INSERT INTO orders (customer_phone, customer_name, order_type, status, total_price, delivery_address) VALUES
('555-111-2222', 'John Doe', 1, 80, 2900, NULL)
ON CONFLICT DO NOTHING;

-- Get the ID for the inserted order
DO $$
DECLARE
    order_id INTEGER;
    order_item_id INTEGER;
BEGIN
    SELECT id INTO order_id FROM orders WHERE customer_phone = '555-111-2222' LIMIT 1;
    
    -- Insert order items
    INSERT INTO order_items (order_id, menu_item_plu, name, price, quantity)
    VALUES (order_id, 'CALI-ROLL', 'California Roll', 1200, 1)
    RETURNING id INTO order_item_id;
    
    -- Insert order item modifiers
    INSERT INTO order_item_modifiers (order_item_id, modifier_plu, name, price_change, quantity)
    VALUES (order_item_id, 'EXTRA-AVO', 'Extra Avocado', 150, 1);
    
    -- Insert second order item
    INSERT INTO order_items (order_id, menu_item_plu, name, price, quantity)
    VALUES (order_id, 'MISO-SOUP', 'Miso Soup', 500, 1)
    RETURNING id INTO order_item_id;
    
    -- Insert order item modifiers for second item
    INSERT INTO order_item_modifiers (order_item_id, modifier_plu, name, price_change, quantity)
    VALUES (order_item_id, 'SIZE-LRG', 'Large', 300, 1);
END $$;