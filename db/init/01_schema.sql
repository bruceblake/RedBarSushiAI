-- Create tables for RedBarSushiAI

-- Menu Categories Table
CREATE TABLE IF NOT EXISTS menu_categories (
    id SERIAL PRIMARY KEY,
    deliverect_category_id VARCHAR(255),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Menu Items Table
CREATE TABLE IF NOT EXISTS menu_items (
    id SERIAL PRIMARY KEY,
    category_id INTEGER REFERENCES menu_categories(id),
    name VARCHAR(255) NOT NULL,
    reference_handler VARCHAR(255),
    description TEXT,
    price INTEGER NOT NULL,
    plu VARCHAR(255) NOT NULL UNIQUE,  -- Ensure PLU is unique
    deliverect_item_id VARCHAR(255),
    is_available BOOLEAN DEFAULT TRUE,
    is_combo BOOLEAN DEFAULT FALSE,
    is_variant BOOLEAN DEFAULT FALSE,
    image_url TEXT,
    snoozed_until TIMESTAMP WITH TIME ZONE,
    available BOOLEAN DEFAULT TRUE,
    snoozed BOOLEAN DEFAULT FALSE,
    is_category BOOLEAN DEFAULT FALSE,
    snooze_start TIMESTAMP WITH TIME ZONE,
    snooze_end TIMESTAMP WITH TIME ZONE,
    category VARCHAR(255),
    parent_id VARCHAR(255),
    location_id VARCHAR(36),
    properties JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Menu Modifier Groups Table
CREATE TABLE IF NOT EXISTS menu_modifier_groups (
    id SERIAL PRIMARY KEY,
    deliverect_group_id VARCHAR(255),
    name VARCHAR(255) NOT NULL,
    reference_handler VARCHAR(255),
    min_selection INTEGER DEFAULT 0,
    max_selection INTEGER DEFAULT 0,
    multi_max INTEGER DEFAULT 1,
    min_allowed INTEGER DEFAULT 0,
    max_allowed INTEGER,
    plu VARCHAR(255),
    is_variant_group BOOLEAN DEFAULT FALSE,
    location_id VARCHAR(36),
    properties JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Menu Modifiers Table
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
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT menu_modifiers_plu_unique UNIQUE (plu)  -- Add unique constraint
);

-- Item Modifier Groups Table
CREATE TABLE IF NOT EXISTS item_modifier_groups (
    id SERIAL PRIMARY KEY,
    menu_item_id INTEGER REFERENCES menu_items(id),
    modifier_group_id INTEGER REFERENCES menu_modifier_groups(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Group Modifiers Table
CREATE TABLE IF NOT EXISTS group_modifiers (
    id SERIAL PRIMARY KEY,
    modifier_group_id INTEGER REFERENCES menu_modifier_groups(id),
    modifier_id INTEGER REFERENCES menu_modifiers(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Menu Name Variants Table
CREATE TABLE IF NOT EXISTS menu_name_variants (
    id SERIAL PRIMARY KEY,
    variant_phrase VARCHAR(255) NOT NULL,
    canonical_name VARCHAR(255) NOT NULL,
    target_plu VARCHAR(255) NOT NULL REFERENCES menu_items(plu),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX menu_name_variants_phrase_idx ON menu_name_variants (variant_phrase);

-- Orders Table
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

-- Order Items Table
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

-- Order Item Modifiers Table
CREATE TABLE IF NOT EXISTS order_item_modifiers (
    id SERIAL PRIMARY KEY,
    order_item_id INTEGER REFERENCES order_items(id),
    modifier_plu VARCHAR(255) REFERENCES menu_modifiers(plu),
    name VARCHAR(255) NOT NULL,
    price_change INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);