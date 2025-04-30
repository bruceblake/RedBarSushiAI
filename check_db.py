#!/usr/bin/env python3
"""
Check database connection and configuration.
"""
from app import create_app, db
from app.models.menu import MenuItem, MenuModifier, MenuModifierGroup

def check_db_connection():
    """Check database connection and print configuration."""
    app = create_app()
    with app.app_context():
        # Print database URL
        print(f"Database URL: {db.engine.url}")
        
        # Test connection
        try:
            connection = db.engine.connect()
            print("Database connection successful!")
            connection.close()
        except Exception as e:
            print(f"Database connection failed: {e}")
            
        # Check if tables exist
        print("\nChecking for menu tables...")
        inspector = db.inspect(db.engine)
        table_names = inspector.get_table_names()
        
        menu_tables = ['menu_items', 'menu_modifiers', 'menu_modifier_groups', 
                      'menu_item_modifiers', 'menu_modifier_group_items']
        
        for table in menu_tables:
            if table in table_names:
                print(f"  ✅ Table '{table}' exists")
                # Get row count
                count = db.session.query(db.func.count()).select_from(db.table(table)).scalar()
                print(f"     Row count: {count}")
            else:
                print(f"  ❌ Table '{table}' does not exist")
        
if __name__ == "__main__":
    check_db_connection()