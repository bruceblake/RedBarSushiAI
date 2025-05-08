-- Initial database schema for RedBarSushiAI

-- Menu tables
CREATE TABLE IF NOT EXISTS menu_categories (
    id SERIAL PRIMARY KEY,
    deliverect_category_id VARCHAR(255),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS menu_items (
    id SERIAL PRIMARY KEY,
    category_id INTEGER REFERENCES menu_categories(id),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    price INTEGER NOT NULL,
    plu VARCHAR(255) NOT NULL UNIQUE,
    deliverect_item_id VARCHAR(255),
    is_available BOOLEAN DEFAULT TRUE,
    is_combo BOOLEAN DEFAULT FALSE,
    is_variant BOOLEAN DEFAULT FALSE,
    image_url TEXT,
    snoozed_until TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS menu_modifier_groups (
    id SERIAL PRIMARY KEY,
    deliverect_group_id VARCHAR(255),
    name VARCHAR(255) NOT NULL,
    min_selection INTEGER DEFAULT 0,
    max_selection INTEGER DEFAULT 0,
    multi_max INTEGER DEFAULT 1,
    plu VARCHAR(255),
    is_variant_group BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS menu_modifiers (
    id SERIAL PRIMARY KEY,
    modifier_group_id INTEGER REFERENCES menu_modifier_groups(id),
    name VARCHAR(255) NOT NULL,
    price_change INTEGER NOT NULL,
    plu VARCHAR(255) NOT NULL,
    deliverect_modifier_id VARCHAR(255),
    is_available BOOLEAN DEFAULT TRUE,
    snoozed_until TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS item_modifier_groups (
    id SERIAL PRIMARY KEY,
    menu_item_id INTEGER REFERENCES menu_items(id),
    modifier_group_id INTEGER REFERENCES menu_modifier_groups(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS group_modifiers (
    id SERIAL PRIMARY KEY,
    modifier_group_id INTEGER REFERENCES menu_modifier_groups(id),
    modifier_id INTEGER REFERENCES menu_modifiers(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS menu_name_variants (
    id SERIAL PRIMARY KEY,
    variant_phrase VARCHAR(255) NOT NULL,
    canonical_name VARCHAR(255) NOT NULL,
    target_plu VARCHAR(255) NOT NULL REFERENCES menu_items(plu),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS menu_name_variants_phrase_idx ON menu_name_variants (variant_phrase);

-- Order tables
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    deliverect_channel_order_id VARCHAR(255) UNIQUE,
    customer_phone VARCHAR(20) NOT NULL,
    customer_name VARCHAR(255),
    order_type INTEGER NOT NULL,
    status INTEGER DEFAULT 10,
    total_price INTEGER NOT NULL,
    placed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    estimated_time TIMESTAMP WITH TIME ZONE,
    delivery_address TEXT,
    notes TEXT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS order_items (
    id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id),
    menu_item_plu VARCHAR(255) REFERENCES menu_items(plu),
    name VARCHAR(255) NOT NULL,
    price INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS order_item_modifiers (
    id SERIAL PRIMARY KEY,
    order_item_id INTEGER REFERENCES order_items(id),
    modifier_plu VARCHAR(255) REFERENCES menu_modifiers(plu),
    name VARCHAR(255) NOT NULL,
    price_change INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Location table
CREATE TABLE IF NOT EXISTS locations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    address TEXT,
    phone VARCHAR(20),
    deliverect_channel_link_id VARCHAR(255),
    timezone VARCHAR(50) DEFAULT 'America/New_York',
    business_hours JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create a sample location
INSERT INTO locations (name, address, phone, deliverect_channel_link_id)
VALUES ('Red Bar Sushi', '123 Main Street, New York, NY 10001', '+12125551234', 'sample_channel_link_id')
ON CONFLICT DO NOTHING;