"""
Special import module to avoid circular imports.
Use this module to import models to prevent circular import issues.
"""

from app.models import Location, Order