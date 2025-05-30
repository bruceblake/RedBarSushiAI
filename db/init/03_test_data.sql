-- RedBarSushiAI Test Data Initialization
-- This file populates the database with comprehensive test data

-- Only run in test environment
DO $$
BEGIN
    -- Check if we're in test environment by looking for test database name
    IF current_database() LIKE '%test%' THEN
        -- Reset and regenerate test data
        PERFORM reset_test_data();
        PERFORM generate_test_data();
        
        RAISE NOTICE 'Test data initialized successfully';
    ELSE
        RAISE NOTICE 'Skipping test data initialization - not in test database';
    END IF;
END $$;

-- Additional test scenarios data

-- Insert test conversation sessions
INSERT INTO conversation_sessions (session_id, call_sid, phone_number, customer_name, fsm_state, fsm_context, cart_data)
SELECT 
    'test-session-' || generate_series,
    'CA' || md5(random()::text),
    '+1555' || (1000000 + generate_series)::text,
    'Test Customer ' || generate_series,
    CASE 
        WHEN generate_series % 5 = 0 THEN 'GREETING'
        WHEN generate_series % 5 = 1 THEN 'ORDERING'
        WHEN generate_series % 5 = 2 THEN 'CONFIRMATION'
        WHEN generate_series % 5 = 3 THEN 'FULFILLMENT'
        ELSE 'COMPLETION'
    END,
    '{"test": true}'::jsonb,
    '{"items": []}'::jsonb
FROM generate_series(1, 10)
WHERE current_database() LIKE '%test%';

-- Insert test orders with various statuses
INSERT INTO orders (location_id, customer_name, customer_phone, order_type, status, total_amount, deliverect_channel_order_id)
SELECT
    1,
    'Test Customer ' || generate_series,
    '+1555' || (2000000 + generate_series)::text,
    CASE WHEN generate_series % 2 = 0 THEN 'pickup' ELSE 'delivery' END,
    CASE 
        WHEN generate_series % 4 = 0 THEN 'pending'
        WHEN generate_series % 4 = 1 THEN 'confirmed'
        WHEN generate_series % 4 = 2 THEN 'preparing'
        ELSE 'completed'
    END,
    (20.00 + (generate_series * 5.50)),
    'TEST-ORDER-' || generate_series
FROM generate_series(1, 20)
WHERE current_database() LIKE '%test%';

-- Insert order items for some test orders
INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price, total_price)
SELECT 
    o.id,
    mi.id,
    (random() * 3 + 1)::integer,
    mi.price,
    mi.price * (random() * 3 + 1)::integer
FROM orders o
CROSS JOIN menu_items mi
WHERE o.id <= 5 AND mi.id <= 5 AND current_database() LIKE '%test%';

-- Create test scenarios for edge cases

-- Unavailable items
UPDATE menu_items 
SET is_available = false, snoozed_until = CURRENT_TIMESTAMP + INTERVAL '2 hours'
WHERE plu IN ('ROLL003', 'SASH002')
AND current_database() LIKE '%test%';

-- Items with complex modifier rules
DO $$
DECLARE
    combo_item_id INTEGER;
    combo_group_id INTEGER;
BEGIN
    IF current_database() LIKE '%test%' THEN
        -- Insert a combo item
        INSERT INTO menu_items (category_id, name, description, price, plu, is_combo, is_available)
        VALUES (2, 'Sushi Combo Platter', '12 pieces of assorted sushi', 35.99, 'COMBO001', true, true)
        RETURNING id INTO combo_item_id;
        
        -- Insert a complex modifier group
        INSERT INTO menu_modifier_groups (name, min_selection, max_selection, plu)
        VALUES ('Choose Your Rolls (Pick 3)', 3, 3, 'MODGRP005')
        RETURNING id INTO combo_group_id;
        
        -- Insert modifiers for combo selection
        INSERT INTO menu_modifiers (modifier_group_id, name, price_change, plu) VALUES
        (combo_group_id, 'California Roll (4 pcs)', 0.00, 'MOD014'),
        (combo_group_id, 'Spicy Tuna Roll (4 pcs)', 2.00, 'MOD015'),
        (combo_group_id, 'Philadelphia Roll (4 pcs)', 1.00, 'MOD016'),
        (combo_group_id, 'Dragon Roll (4 pcs)', 4.00, 'MOD017'),
        (combo_group_id, 'Cucumber Roll (4 pcs)', 0.00, 'MOD018');
        
        -- Link combo to modifier group
        INSERT INTO menu_item_modifier_groups (menu_item_id, modifier_group_id)
        VALUES (combo_item_id, combo_group_id);
    END IF;
END $$;

-- Create frequently ordered items for testing recommendations
WITH popular_items AS (
    SELECT id FROM menu_items WHERE plu IN ('ROLL001', 'APP001', 'BEV001') AND current_database() LIKE '%test%'
)
INSERT INTO test_audit_log (test_run_id, action, entity_type, entity_id, new_data)
SELECT 
    'popularity-data',
    'order_count',
    'menu_item',
    id,
    jsonb_build_object('order_count', (random() * 100 + 50)::integer)
FROM popular_items;

-- Create test data for concurrent operations
DO $$
BEGIN
    IF current_database() LIKE '%test%' THEN
        -- Create multiple active sessions
        FOR i IN 1..5 LOOP
            INSERT INTO conversation_sessions (
                session_id, 
                call_sid, 
                phone_number, 
                fsm_state, 
                is_active,
                cart_data
            ) VALUES (
                'concurrent-session-' || i,
                'CA' || md5(i::text),
                '+1555999000' || i,
                'ORDERING',
                true,
                jsonb_build_object(
                    'items', jsonb_build_array(
                        jsonb_build_object(
                            'plu', 'ROLL001',
                            'quantity', i,
                            'modifiers', '[]'::jsonb
                        )
                    )
                )
            );
        END LOOP;
    END IF;
END $$;

-- Add test data for menu matching edge cases
INSERT INTO menu_name_variants (menu_item_id, variant_name)
SELECT 
    mi.id,
    CASE 
        WHEN position(' ' in mi.name) > 0 THEN 
            -- Create acronym variant (e.g., "California Roll" -> "CR")
            array_to_string(
                ARRAY(
                    SELECT substring(word from 1 for 1) 
                    FROM unnest(string_to_array(mi.name, ' ')) AS word
                ), 
                ''
            )
        ELSE 
            -- Create shortened variant
            substring(mi.name from 1 for 4)
    END
FROM menu_items mi
WHERE mi.id <= 10 AND current_database() LIKE '%test%'
ON CONFLICT DO NOTHING;

-- Create view for test statistics
CREATE OR REPLACE VIEW test_statistics AS
SELECT 
    'menu_items' as entity_type,
    COUNT(*) as total_count,
    COUNT(*) FILTER (WHERE is_available = true) as available_count,
    COUNT(*) FILTER (WHERE is_combo = true) as combo_count
FROM menu_items
WHERE current_database() LIKE '%test%'
UNION ALL
SELECT 
    'orders' as entity_type,
    COUNT(*) as total_count,
    COUNT(*) FILTER (WHERE status = 'completed') as available_count,
    COUNT(*) FILTER (WHERE order_type = 'delivery') as combo_count
FROM orders
WHERE current_database() LIKE '%test%'
UNION ALL
SELECT 
    'active_sessions' as entity_type,
    COUNT(*) as total_count,
    COUNT(*) FILTER (WHERE fsm_state = 'ORDERING') as available_count,
    0 as combo_count
FROM conversation_sessions
WHERE is_active = true AND current_database() LIKE '%test%';

-- Output test data summary
DO $$
DECLARE
    item_count INTEGER;
    order_count INTEGER;
    session_count INTEGER;
BEGIN
    IF current_database() LIKE '%test%' THEN
        SELECT COUNT(*) INTO item_count FROM menu_items;
        SELECT COUNT(*) INTO order_count FROM orders;
        SELECT COUNT(*) INTO session_count FROM conversation_sessions;
        
        RAISE NOTICE 'Test data summary:';
        RAISE NOTICE '  Menu items: %', item_count;
        RAISE NOTICE '  Orders: %', order_count;
        RAISE NOTICE '  Sessions: %', session_count;
    END IF;
END $$;