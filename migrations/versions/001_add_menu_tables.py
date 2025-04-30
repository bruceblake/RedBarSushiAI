"""
Add menu tables migration

Revision ID: 001
Revises: 
Create Date: 2025-04-30

This migration adds database tables for storing menu items, modifiers, and modifier groups.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# Try to import JSONB for PostgreSQL, but provide fallback for SQLite
try:
    from sqlalchemy.dialects.postgresql import JSONB
    has_jsonb = True
except ImportError:
    has_jsonb = False


# revision identifiers, used by Alembic
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # First determine if we're using PostgreSQL or SQLite
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    dialect = inspector.dialect.name
    
    # Use JSONB for PostgreSQL, TEXT for other databases like SQLite
    properties_column = sa.Column('properties', JSONB) if dialect == 'postgresql' and has_jsonb else sa.Column('properties', sa.Text)
    
    # Create menu_items table
    op.create_table('menu_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('reference_handler', sa.String(length=255), nullable=True),
        sa.Column('plu', sa.String(length=255), nullable=True),
        sa.Column('price', sa.Float(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(length=255), nullable=True),
        sa.Column('parent_id', sa.String(length=255), nullable=True),
        sa.Column('available', sa.Boolean(), default=True),
        sa.Column('snoozed', sa.Boolean(), default=False),
        sa.Column('is_category', sa.Boolean(), default=False),
        sa.Column('is_variant', sa.Boolean(), default=False),
        sa.Column('snooze_start', sa.DateTime(), nullable=True),
        sa.Column('snooze_end', sa.DateTime(), nullable=True),
        sa.Column('snooze_until', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.current_timestamp(), onupdate=sa.func.current_timestamp()),
        sa.Column('location_id', sa.String(length=36), nullable=True),
        properties_column,
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for menu_items
    op.create_index('ix_menu_items_reference_handler', 'menu_items', ['reference_handler'])
    op.create_index('ix_menu_items_plu', 'menu_items', ['plu'])
    
    # Create menu_modifiers table
    op.create_table('menu_modifiers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('reference_handler', sa.String(length=255), nullable=True),
        sa.Column('price', sa.Float(), nullable=True),
        sa.Column('available', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.current_timestamp(), onupdate=sa.func.current_timestamp()),
        sa.Column('location_id', sa.String(length=36), nullable=True),
        properties_column,
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for menu_modifiers
    op.create_index('ix_menu_modifiers_reference_handler', 'menu_modifiers', ['reference_handler'])
    
    # Create menu_modifier_groups table
    op.create_table('menu_modifier_groups',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('reference_handler', sa.String(length=255), nullable=True),
        sa.Column('min_allowed', sa.Integer(), default=0),
        sa.Column('max_allowed', sa.Integer(), nullable=True),
        sa.Column('multi_max', sa.Integer(), default=1),
        sa.Column('is_variant_group', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.current_timestamp(), onupdate=sa.func.current_timestamp()),
        sa.Column('location_id', sa.String(length=36), nullable=True),
        properties_column,
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for menu_modifier_groups
    op.create_index('ix_menu_modifier_groups_reference_handler', 'menu_modifier_groups', ['reference_handler'])
    
    # Create association table for menu_items and menu_modifier_groups
    op.create_table('menu_item_modifiers',
        sa.Column('menu_item_id', sa.Integer(), nullable=False),
        sa.Column('menu_modifier_group_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['menu_item_id'], ['menu_items.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['menu_modifier_group_id'], ['menu_modifier_groups.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('menu_item_id', 'menu_modifier_group_id')
    )
    
    # Create association table for menu_modifier_groups and menu_modifiers
    op.create_table('menu_modifier_group_items',
        sa.Column('menu_modifier_group_id', sa.Integer(), nullable=False),
        sa.Column('menu_modifier_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['menu_modifier_group_id'], ['menu_modifier_groups.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['menu_modifier_id'], ['menu_modifiers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('menu_modifier_group_id', 'menu_modifier_id')
    )


def downgrade():
    # Drop all tables in reverse order
    op.drop_table('menu_modifier_group_items')
    op.drop_table('menu_item_modifiers')
    op.drop_table('menu_modifier_groups')
    op.drop_table('menu_modifiers')
    op.drop_table('menu_items')