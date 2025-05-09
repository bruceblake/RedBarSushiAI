-- SQL migration script to add the missing reference_handler column to menu_modifiers table

-- Add reference_handler column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT FROM information_schema.columns 
        WHERE table_name = 'menu_modifiers' AND column_name = 'reference_handler'
    ) THEN
        ALTER TABLE menu_modifiers ADD COLUMN reference_handler TEXT;
        
        -- Log the change
        RAISE NOTICE 'Added reference_handler column to menu_modifiers table';
    ELSE
        RAISE NOTICE 'reference_handler column already exists in menu_modifiers table';
    END IF;
END
$$;