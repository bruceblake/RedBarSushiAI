-- Add missing columns to menu tables

-- Add location_id to menu_categories
ALTER TABLE menu_categories ADD COLUMN IF NOT EXISTS location_id VARCHAR(255);
CREATE INDEX IF NOT EXISTS idx_menu_categories_location ON menu_categories(location_id);

-- Add order_index to menu_categories
ALTER TABLE menu_categories ADD COLUMN IF NOT EXISTS order_index INTEGER DEFAULT 0;

-- Add properties to menu_categories
ALTER TABLE menu_categories ADD COLUMN IF NOT EXISTS properties JSONB DEFAULT '{}';

-- Add location_id to menu_items
ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS location_id VARCHAR(255);
CREATE INDEX IF NOT EXISTS idx_menu_items_location ON menu_items(location_id);

-- Add order_index to menu_items
ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS order_index INTEGER DEFAULT 0;

-- Add properties to menu_items
ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS properties JSONB DEFAULT '{}';

-- Add is_variant to menu_items
ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS is_variant BOOLEAN DEFAULT FALSE;

-- Add multiMax to menu_modifier_groups
ALTER TABLE menu_modifier_groups ADD COLUMN IF NOT EXISTS "multiMax" INTEGER DEFAULT 1;

-- Add is_variant_group to menu_modifier_groups
ALTER TABLE menu_modifier_groups ADD COLUMN IF NOT EXISTS is_variant_group BOOLEAN DEFAULT FALSE;

-- Add properties to menu_modifier_groups
ALTER TABLE menu_modifier_groups ADD COLUMN IF NOT EXISTS properties JSONB DEFAULT '{}';

-- Add location_id to menu_modifiers
ALTER TABLE menu_modifiers ADD COLUMN IF NOT EXISTS location_id VARCHAR(255);
CREATE INDEX IF NOT EXISTS idx_menu_modifiers_location ON menu_modifiers(location_id);

-- Add properties to menu_modifiers
ALTER TABLE menu_modifiers ADD COLUMN IF NOT EXISTS properties JSONB DEFAULT '{}';