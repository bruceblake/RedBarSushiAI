# Database Migration Guide

This guide explains how to migrate an existing RedBarSushiAI deployment to work with the new database schema that includes additional columns for enhanced order tracking.

## Background

The system has been enhanced to track more detailed information about orders, including:
- Numeric status codes from Deliverect
- Delivery-specific status tracking
- Courier information for delivery orders
- Estimated delivery times

These enhancements require adding new columns to the `Order` table in the database.

## Migration Options

### Option 1: Run the Migration Script (Recommended)

The simplest way to update your database is to run the provided migration script:

```bash
# From the project root directory
python migrate_db.py
```

The script will:
1. Connect to your database (using the `DATABASE_URL` environment variable)
2. Check for missing columns
3. Add any new columns that aren't already present
4. Report what changes were made

Example output:
```
2025-04-09 12:34:56 - INFO - Starting database migration
2025-04-09 12:34:56 - INFO - Connecting to database: postgresql://user:password@host:port/dbname
2025-04-09 12:34:56 - INFO - Added column status_code to "order".
2025-04-09 12:34:56 - INFO - Added column status_updated_at to "order".
2025-04-09 12:34:56 - INFO - Added column delivery_status to "order".
2025-04-09 12:34:56 - INFO - Added column delivery_status_code to "order".
2025-04-09 12:34:56 - INFO - Added column courier_name to "order".
2025-04-09 12:34:56 - INFO - Added column courier_phone to "order".
2025-04-09 12:34:56 - INFO - Added column estimated_delivery_time to "order".
2025-04-09 12:34:56 - INFO - Migration completed successfully!
```

### Option 2: Manual SQL Migration

If you prefer to run the SQL migration manually, you can use the following SQL commands:

```sql
-- Add status tracking columns
ALTER TABLE "order" ADD COLUMN IF NOT EXISTS status_code INTEGER NULL;
ALTER TABLE "order" ADD COLUMN IF NOT EXISTS status_updated_at TIMESTAMP NULL;

-- Add delivery tracking columns
ALTER TABLE "order" ADD COLUMN IF NOT EXISTS delivery_status VARCHAR(30) NULL;
ALTER TABLE "order" ADD COLUMN IF NOT EXISTS delivery_status_code INTEGER NULL;
ALTER TABLE "order" ADD COLUMN IF NOT EXISTS courier_name VARCHAR(50) NULL;
ALTER TABLE "order" ADD COLUMN IF NOT EXISTS courier_phone VARCHAR(20) NULL;
ALTER TABLE "order" ADD COLUMN IF NOT EXISTS estimated_delivery_time TIMESTAMP NULL;

-- Commit the changes
COMMIT;
```

### Option 3: Rely on Automatic Fallbacks

The system includes fallback mechanisms that will allow it to continue functioning even if the database hasn't been migrated. However, this approach will:

1. Generate more error messages in the logs
2. Fall back to legacy status tracking (less detailed status information)
3. Not track delivery-specific information
4. Not display courier details to customers

The fallbacks are designed as a temporary measure to avoid downtime, but running the migration is recommended for full functionality.

## Verifying the Migration

To verify the migration was successful, you can:

1. Check the database schema:
   ```sql
   \d "order"
   ```

2. Look for the new columns in the output:
   ```
   Column                  | Type                        | Modifiers
   ------------------------+----------------------------+-----------------------------
   id                      | character varying(36)       | not null
   ...
   status_code             | integer                     |
   status_updated_at       | timestamp without time zone |
   delivery_status         | character varying(30)       |
   delivery_status_code    | integer                     |
   courier_name            | character varying(50)       |
   courier_phone           | character varying(20)       |
   estimated_delivery_time | timestamp without time zone |
   ...
   ```

3. Test an order status update:
   ```bash
   # Start the application and check that order status updates work correctly
   curl -X POST http://your-app-url/order_status \
     -H "Content-Type: application/json" \
     -d '{"channelOrderId":"some-order-id","status":"ACCEPTED","code":20}'
   ```

## Troubleshooting

### Database Connection Issues

If the migration script can't connect to your database:

1. Check that the `DATABASE_URL` environment variable is set correctly:
   ```bash
   echo $DATABASE_URL
   ```

2. Try providing the connection string directly:
   ```bash
   DATABASE_URL=postgresql://username:password@hostname:port/database python migrate_db.py
   ```

### Permission Issues

If you see errors about permissions:

1. Make sure the database user has ALTER TABLE privileges
2. Run the SQL commands manually as a user with sufficient privileges

### Migration Not Working

If orders still don't track detailed status after migration:

1. Check the application logs for errors
2. Verify that the status codes are being sent correctly from Deliverect
3. Restart the application to ensure it recognizes the new schema