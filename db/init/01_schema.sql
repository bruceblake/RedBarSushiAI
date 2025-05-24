-- RedBarSushiAI Database Schema

-- Menu Categories
CREATE TABLE IF NOT EXISTS menu_categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    deliverect_category_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Menu Items
CREATE TABLE IF NOT EXISTS menu_items (
    id SERIAL PRIMARY KEY,
    category_id INTEGER REFERENCES menu_categories(id),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    price NUMERIC(10, 2) NOT NULL,
    plu VARCHAR(50) UNIQUE,
    deliverect_item_id VARCHAR(100),
    is_available BOOLEAN DEFAULT TRUE,
    is_combo BOOLEAN DEFAULT FALSE,
    is_variant BOOLEAN DEFAULT FALSE,
    image_url TEXT,
    snoozed_until TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Menu Modifier Groups
CREATE TABLE IF NOT EXISTS menu_modifier_groups (
    id SERIAL PRIMARY KEY,
    deliverect_group_id VARCHAR(100),
    name VARCHAR(100) NOT NULL,
    min_selection INTEGER DEFAULT 0,
    max_selection INTEGER DEFAULT 1,
    multi_max INTEGER,
    plu VARCHAR(50),
    is_variant_group BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Menu Modifiers
CREATE TABLE IF NOT EXISTS menu_modifiers (
    id SERIAL PRIMARY KEY,
    modifier_group_id INTEGER REFERENCES menu_modifier_groups(id),
    name VARCHAR(100) NOT NULL,
    price_change NUMERIC(10, 2) DEFAULT 0,
    plu VARCHAR(50) UNIQUE,
    deliverect_modifier_id VARCHAR(100),
    is_available BOOLEAN DEFAULT TRUE,
    snoozed_until TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Add sample data
INSERT INTO menu_categories (name, description) 
VALUES ('Rolls', 'Sushi rolls') 
ON CONFLICT DO NOTHING;

INSERT INTO menu_items (name, description, price, plu, category_id) 
VALUES ('California Roll', 'Crab, avocado, and cucumber', 12.99, 'CALROLL', 1) 
ON CONFLICT DO NOTHING;