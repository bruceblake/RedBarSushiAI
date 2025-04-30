# Database Migrations

This directory contains the Alembic migration scripts for database schema changes.

## Running Migrations

To run migrations, use the Flask-Migrate CLI commands:

```
flask db upgrade    # Apply all pending migrations
flask db downgrade  # Revert the last migration
flask db migrate    # Generate a new migration based on model changes
flask db init       # Initialize migrations (only needed for first setup)
```

## Migration Files

- `env.py` - Environment configuration for Alembic
- `versions/` - Contains all migration scripts
- `alembic.ini` - Alembic configuration file (created by Flask-Migrate)

## Adding New Models

When adding new models:
1. Create the model class in the appropriate file
2. Import the model in the app models module
3. Generate a migration: `flask db migrate -m "Add new model"`
4. Review the generated migration script in versions/
5. Apply the migration: `flask db upgrade`