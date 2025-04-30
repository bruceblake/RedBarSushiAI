"""
CLI commands for managing the application.
"""

import os
import click
import json
import logging
from flask import current_app
from flask.cli import with_appcontext

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@click.command('init-menu-db')
@with_appcontext
def init_menu_db():
    """Initialize menu database from menu_data.json file."""
    try:
        from app.utils.menu_db_store import menu_db_store
        
        # Check if menu database already has data
        menu_data = menu_db_store.get_menu_data()
        
        if menu_data.get("items"):
            item_count = len(menu_data["items"])
            click.echo(f"Menu database already contains {item_count} items.")
            
            # Ask for confirmation to overwrite
            if not click.confirm("Do you want to re-initialize the database?"):
                click.echo("Operation cancelled.")
                return
        
        # Find menu_data.json file
        menu_file = None
        potential_paths = [
            os.path.join(os.getcwd(), "menu_data.json"),
            os.path.join(os.path.dirname(os.getcwd()), "menu_data.json"),
            "/home/proxyie/MySoftware/RedBarSushiAI/menu_data.json",
            current_app.config.get("MENU_FILE_PATH", "")
        ]
        
        for path in potential_paths:
            if os.path.exists(path):
                menu_file = path
                break
        
        if not menu_file:
            click.echo("Error: Could not find menu_data.json file.")
            return
            
        click.echo(f"Loading menu data from {menu_file}...")
        
        # Read the JSON file
        with open(menu_file, 'r') as f:
            file_menu_data = json.load(f)
            
        # Store in database
        if menu_db_store.store_menu_data(file_menu_data):
            click.echo(f"Successfully initialized menu database with {len(file_menu_data.get('items', []))} items.")
        else:
            click.echo("Error: Failed to store menu data in database.")
            
    except Exception as e:
        click.echo(f"Error: {str(e)}")


@click.command('export-menu')
@click.argument('output_file', default='menu_export.json')
@with_appcontext
def export_menu(output_file):
    """Export menu data from database to a JSON file."""
    try:
        from app.utils.menu_db_store import menu_db_store
        
        # Get menu data from database
        menu_data = menu_db_store.get_menu_data(force_refresh=True)
        
        if not menu_data.get("items"):
            click.echo("Warning: No menu items found in the database.")
            if not click.confirm("Continue with empty export?"):
                click.echo("Operation cancelled.")
                return
        
        # Write to the file
        with open(output_file, 'w') as f:
            json.dump(menu_data, f, indent=2)
            
        click.echo(f"Successfully exported {len(menu_data.get('items', []))} menu items to {output_file}.")
        
    except Exception as e:
        click.echo(f"Error: {str(e)}")


def register_commands(app):
    """Register CLI commands with the Flask application."""
    app.cli.add_command(init_menu_db)
    app.cli.add_command(export_menu)