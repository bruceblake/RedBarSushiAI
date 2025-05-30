-- RedBarSushiAI Test Database Schema Extensions
-- This file contains additional schema and data specifically for testing

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Locations table (for multi-location testing)
CREATE TABLE IF NOT EXISTS locations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    address TEXT,
    phone VARCHAR(20),
    deliverect_location_id VARCHAR(100) UNIQUE,
    deliverect_channel_id VARCHAR(100),
    deliverect_api_key TEXT,
    business_hours JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Menu Name Variants (for fuzzy matching)
CREATE TABLE IF NOT EXISTS menu_name_variants (
    id SERIAL PRIMARY KEY,
    menu_item_id INTEGER REFERENCES menu_items(id) ON DELETE CASCADE,
    variant_name VARCHAR(255) NOT NULL,
    is_primary BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(menu_item_id, variant_name)
);

-- Orders table
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    order_uuid UUID DEFAULT uuid_generate_v4() UNIQUE,
    location_id INTEGER REFERENCES locations(id),
    customer_name VARCHAR(255),
    customer_phone VARCHAR(20),
    customer_email VARCHAR(255),
    order_type VARCHAR(20) CHECK (order_type IN ('pickup', 'delivery')),
    status VARCHAR(50) DEFAULT 'pending',
    total_amount NUMERIC(10, 2),
    tax_amount NUMERIC(10, 2),
    delivery_fee NUMERIC(10, 2),
    delivery_address TEXT,
    delivery_instructions TEXT,
    estimated_ready_time TIMESTAMP,
    deliverect_channel_order_id VARCHAR(100),
    deliverect_order_id VARCHAR(100),
    payment_method VARCHAR(50),
    payment_status VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Order Items table
CREATE TABLE IF NOT EXISTS order_items (
    id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id) ON DELETE CASCADE,
    menu_item_id INTEGER REFERENCES menu_items(id),
    quantity INTEGER NOT NULL DEFAULT 1,
    unit_price NUMERIC(10, 2) NOT NULL,
    total_price NUMERIC(10, 2) NOT NULL,
    special_instructions TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Order Item Modifiers table
CREATE TABLE IF NOT EXISTS order_item_modifiers (
    id SERIAL PRIMARY KEY,
    order_item_id INTEGER REFERENCES order_items(id) ON DELETE CASCADE,
    modifier_id INTEGER REFERENCES menu_modifiers(id),
    quantity INTEGER NOT NULL DEFAULT 1,
    price_change NUMERIC(10, 2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Conversation Sessions table (for FSM state persistence)
CREATE TABLE IF NOT EXISTS conversation_sessions (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) UNIQUE NOT NULL,
    call_sid VARCHAR(255),
    phone_number VARCHAR(20),
    customer_name VARCHAR(255),
    fsm_state VARCHAR(50),
    fsm_context JSONB,
    conversation_history JSONB,
    cart_data JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP,
    last_activity_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Test Audit Log table
CREATE TABLE IF NOT EXISTS test_audit_log (
    id SERIAL PRIMARY KEY,
    test_run_id VARCHAR(255),
    action VARCHAR(100),
    entity_type VARCHAR(50),
    entity_id INTEGER,
    old_data JSONB,
    new_data JSONB,
    user_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Many-to-many relationship: Items to Modifier Groups
CREATE TABLE IF NOT EXISTS menu_item_modifier_groups (
    menu_item_id INTEGER REFERENCES menu_items(id) ON DELETE CASCADE,
    modifier_group_id INTEGER REFERENCES menu_modifier_groups(id) ON DELETE CASCADE,
    display_order INTEGER DEFAULT 0,
    PRIMARY KEY (menu_item_id, modifier_group_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_menu_items_plu ON menu_items(plu);
CREATE INDEX IF NOT EXISTS idx_menu_items_category ON menu_items(category_id);
CREATE INDEX IF NOT EXISTS idx_menu_items_available ON menu_items(is_available);
CREATE INDEX IF NOT EXISTS idx_menu_name_variants_name ON menu_name_variants(variant_name);
CREATE INDEX IF NOT EXISTS idx_orders_customer_phone ON orders(customer_phone);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at);
CREATE INDEX IF NOT EXISTS idx_conversation_sessions_session_id ON conversation_sessions(session_id);
CREATE INDEX IF NOT EXISTS idx_conversation_sessions_call_sid ON conversation_sessions(call_sid);

-- Functions for testing
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for updated_at
CREATE TRIGGER update_menu_categories_updated_at BEFORE UPDATE ON menu_categories 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_menu_items_updated_at BEFORE UPDATE ON menu_items 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_menu_modifier_groups_updated_at BEFORE UPDATE ON menu_modifier_groups 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_menu_modifiers_updated_at BEFORE UPDATE ON menu_modifiers 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_locations_updated_at BEFORE UPDATE ON locations 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_orders_updated_at BEFORE UPDATE ON orders 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Test helper functions
CREATE OR REPLACE FUNCTION reset_test_data()
RETURNS void AS $$
BEGIN
    -- Clear test data in reverse order of dependencies
    DELETE FROM test_audit_log;
    DELETE FROM order_item_modifiers;
    DELETE FROM order_items;
    DELETE FROM orders;
    DELETE FROM conversation_sessions;
    DELETE FROM menu_name_variants;
    DELETE FROM menu_item_modifier_groups;
    DELETE FROM menu_modifiers;
    DELETE FROM menu_modifier_groups;
    DELETE FROM menu_items;
    DELETE FROM menu_categories;
    DELETE FROM locations;
    
    -- Reset sequences
    ALTER SEQUENCE menu_categories_id_seq RESTART WITH 1;
    ALTER SEQUENCE menu_items_id_seq RESTART WITH 1;
    ALTER SEQUENCE menu_modifier_groups_id_seq RESTART WITH 1;
    ALTER SEQUENCE menu_modifiers_id_seq RESTART WITH 1;
    ALTER SEQUENCE locations_id_seq RESTART WITH 1;
    ALTER SEQUENCE orders_id_seq RESTART WITH 1;
    ALTER SEQUENCE order_items_id_seq RESTART WITH 1;
    ALTER SEQUENCE order_item_modifiers_id_seq RESTART WITH 1;
    ALTER SEQUENCE conversation_sessions_id_seq RESTART WITH 1;
    ALTER SEQUENCE test_audit_log_id_seq RESTART WITH 1;
END;
$$ LANGUAGE plpgsql;

-- Function to generate test data
CREATE OR REPLACE FUNCTION generate_test_data()
RETURNS void AS $$
BEGIN
    -- Insert test location
    INSERT INTO locations (name, address, phone, deliverect_location_id, business_hours, is_active)
    VALUES (
        'Red Bar Sushi - Test Location',
        '123 Test Street, Test City, TC 12345',
        '+15551234567',
        'test-location-001',
        '{"monday": {"open": "11:00", "close": "22:00"}, "tuesday": {"open": "11:00", "close": "22:00"}}',
        true
    );

    -- Insert test categories
    INSERT INTO menu_categories (name, description, deliverect_category_id) VALUES
    ('Appetizers', 'Start your meal with these delicious options', 'cat-appetizers'),
    ('Sushi Rolls', 'Fresh and creative sushi rolls', 'cat-rolls'),
    ('Sashimi', 'Fresh sliced fish', 'cat-sashimi'),
    ('Beverages', 'Drinks and refreshments', 'cat-beverages'),
    ('Desserts', 'Sweet endings', 'cat-desserts');

    -- Insert test menu items
    INSERT INTO menu_items (category_id, name, description, price, plu, deliverect_item_id, is_available) VALUES
    -- Appetizers
    (1, 'Edamame', 'Steamed soybeans with sea salt', 5.99, 'APP001', 'item-edamame', true),
    (1, 'Gyoza', 'Pan-fried pork dumplings (6 pcs)', 7.99, 'APP002', 'item-gyoza', true),
    (1, 'Miso Soup', 'Traditional soybean soup', 3.99, 'APP003', 'item-miso', true),
    -- Sushi Rolls
    (2, 'California Roll', 'Crab, avocado, and cucumber', 12.99, 'ROLL001', 'item-california', true),
    (2, 'Spicy Tuna Roll', 'Tuna with spicy mayo', 14.99, 'ROLL002', 'item-spicy-tuna', true),
    (2, 'Dragon Roll', 'Eel, cucumber, topped with avocado', 18.99, 'ROLL003', 'item-dragon', true),
    (2, 'Philadelphia Roll', 'Salmon, cream cheese, cucumber', 13.99, 'ROLL004', 'item-philly', true),
    -- Sashimi
    (3, 'Salmon Sashimi', 'Fresh salmon (6 pcs)', 15.99, 'SASH001', 'item-salmon-sash', true),
    (3, 'Tuna Sashimi', 'Fresh tuna (6 pcs)', 17.99, 'SASH002', 'item-tuna-sash', true),
    -- Beverages
    (4, 'Green Tea', 'Hot green tea', 2.99, 'BEV001', 'item-green-tea', true),
    (4, 'Soda', 'Coca-Cola, Sprite, or Orange', 3.99, 'BEV002', 'item-soda', true),
    -- Desserts
    (5, 'Mochi Ice Cream', 'Green tea, mango, or red bean (2 pcs)', 6.99, 'DES001', 'item-mochi', true);

    -- Insert modifier groups
    INSERT INTO menu_modifier_groups (name, min_selection, max_selection, deliverect_group_id, plu) VALUES
    ('Roll Additions', 0, 3, 'modgroup-additions', 'MODGRP001'),
    ('Spice Level', 0, 1, 'modgroup-spice', 'MODGRP002'),
    ('Soda Selection', 1, 1, 'modgroup-soda', 'MODGRP003'),
    ('Mochi Flavors', 1, 2, 'modgroup-mochi', 'MODGRP004');

    -- Insert modifiers
    INSERT INTO menu_modifiers (modifier_group_id, name, price_change, plu, deliverect_modifier_id) VALUES
    -- Roll Additions
    (1, 'Extra Avocado', 2.00, 'MOD001', 'mod-extra-avo'),
    (1, 'Spicy Mayo', 1.00, 'MOD002', 'mod-spicy-mayo'),
    (1, 'Tempura Flakes', 1.50, 'MOD003', 'mod-tempura'),
    (1, 'No Wasabi', 0.00, 'MOD004', 'mod-no-wasabi'),
    -- Spice Level
    (2, 'Mild', 0.00, 'MOD005', 'mod-mild'),
    (2, 'Medium', 0.00, 'MOD006', 'mod-medium'),
    (2, 'Hot', 0.00, 'MOD007', 'mod-hot'),
    -- Soda Selection
    (3, 'Coca-Cola', 0.00, 'MOD008', 'mod-coke'),
    (3, 'Sprite', 0.00, 'MOD009', 'mod-sprite'),
    (3, 'Orange Fanta', 0.00, 'MOD010', 'mod-orange'),
    -- Mochi Flavors
    (4, 'Green Tea', 0.00, 'MOD011', 'mod-mochi-green'),
    (4, 'Mango', 0.00, 'MOD012', 'mod-mochi-mango'),
    (4, 'Red Bean', 0.00, 'MOD013', 'mod-mochi-red');

    -- Link items to modifier groups
    -- All rolls can have additions and spice level
    INSERT INTO menu_item_modifier_groups (menu_item_id, modifier_group_id) 
    SELECT mi.id, mg.id 
    FROM menu_items mi 
    CROSS JOIN menu_modifier_groups mg 
    WHERE mi.category_id = 2 AND mg.id IN (1, 2);

    -- Soda needs selection
    INSERT INTO menu_item_modifier_groups (menu_item_id, modifier_group_id) VALUES
    (11, 3);  -- Soda -> Soda Selection

    -- Mochi needs flavor selection
    INSERT INTO menu_item_modifier_groups (menu_item_id, modifier_group_id) VALUES
    (12, 4);  -- Mochi -> Mochi Flavors

    -- Insert name variants for better matching
    INSERT INTO menu_name_variants (menu_item_id, variant_name, is_primary) VALUES
    (4, 'Cali Roll', false),
    (4, 'California', false),
    (5, 'Spicy Tuna', true),
    (5, 'Tuna Roll Spicy', false),
    (6, 'Dragon', false),
    (7, 'Philly Roll', false),
    (7, 'Philadelphia', false);

END;
$$ LANGUAGE plpgsql;

-- Grant permissions for test user
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO redbarsushi;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO redbarsushi;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO redbarsushi;