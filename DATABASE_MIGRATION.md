# PostgreSQL Menu Database Migration Guide

This document outlines the process of migrating the menu data system from using JSON files to using the PostgreSQL database.

## Prerequisites

- PostgreSQL database server running and accessible
- Database connection configured in the application
- Python environment with all requirements installed

## Database Configuration

The application will use the standard database connection parameters defined in the application configuration. For Render environments, it will use the `RENDER_DATABASE_URL` environment variable.

Make sure your database URL is configured in one of the following ways:
- `RENDER_DATABASE_URL` environment variable (recommended for Render environments)
- `DATABASE_URL` or `SQLALCHEMY_DATABASE_URI` environment variables
- Individual components: `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, and `DB_NAME` environment variables

## Migration Process

### 1. Running the Migration Script

The migration script `database_menu_integration.py` handles the entire process:

```bash
# Basic migration
python database_menu_integration.py

# Force migration even if database already has data
python database_menu_integration.py --force

# Associate the menu data with a specific location
python database_menu_integration.py --location-id your_location_id

# Skip updating the configuration files
python database_menu_integration.py --skip-config
```

### 2. Migration Steps

The script performs the following steps:

1. **Initialize Database Tables**: Creates necessary database tables for menu items, modifiers, and modifier groups.
2. **Migrate Menu Data**: Transfers data from the JSON file to the database tables.
3. **Verify Migration**: Checks that all data was successfully migrated.
4. **Backup Original Files**: Creates backups of original JSON and Python files.
5. **Update Configuration**: Sets up the application to use the database-backed implementation.

### 3. Troubleshooting

If the migration fails, check the following:

- Database connection: Ensure PostgreSQL is running and accessible
- Database permissions: Verify the database user has sufficient privileges
- Log file: Check `menu_migration_*.log` for detailed error information
- File paths: Make sure the script is run from the project root directory

## Reverting the Migration

If you need to revert to the file-based approach:

1. Restore the original `menu_utils.py` file from the backup:
   ```bash
   # Find the backup file
   ls -la app/utils/menu_utils.py.bak.*
   
   # Restore the original file
   cp app/utils/menu_utils.py.bak.TIMESTAMP app/utils/menu_utils.py
   ```

2. The original menu data JSON file should still be available as a backup.

## Verifying the Migration

To verify that the application is correctly using the database for menu data:

1. **Check for Database Access**: The application logs should show database queries when menu operations are performed.
2. **Update a Menu Item**: Make changes to a menu item and verify they persist after restarting the application.
3. **Run Tests**: Execute existing tests to ensure everything works with the database-backed implementation.

## Database Schema

The menu data is stored in the following tables:

- `menu_items`: Individual menu items with their properties
- `menu_modifiers`: Menu modifiers (e.g., toppings, options)
- `menu_modifier_groups`: Groupings of modifiers with constraints
- Association tables for many-to-many relationships between items and modifiers

## Performance Considerations

The database implementation includes multiple layers of caching:

1. **Redis Caching**: Fast key-value store for frequently accessed menu data
2. **In-Memory Fallback**: Local memory cache when Redis is unavailable
3. **Database Query Optimization**: Efficient querying patterns

This ensures the database-backed implementation maintains similar performance characteristics to the file-based approach.

## Deployment Notes

When deploying to Render:

1. Make sure the `RENDER_DATABASE_URL` environment variable is correctly set
2. Run the migration script once after deployment
3. Monitor the application logs to ensure everything is working properly

For other deployment environments, ensure the appropriate database connection environment variables are set.