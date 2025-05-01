"""
Special import module to avoid circular imports.
Use this module to import models to prevent circular import issues.
"""

# Direct model class creation instead of import to avoid circular imports
# This is a replica of the Location model from app/models.py
from app import db
from sqlalchemy.ext.declarative import declarative_base
import json

Base = declarative_base()

# Mock the query interface that SQLAlchemy provides
class QueryMock:
    def __init__(self, model_class):
        self.model_class = model_class
    
    def filter_by(self, **kwargs):
        self.filters = kwargs
        return self
    
    def first(self):
        # Directly query the database for the Location
        try:
            conn = db.engine.connect()
            params = {}
            where_clause = ""
            for k, v in self.filters.items():
                params[k] = v
                where_clause += f"{k} = :{k} AND "
            
            where_clause = where_clause[:-5] if where_clause else ""
            
            query = f"SELECT id, name, status, webhook_base, api_key FROM \"location\" WHERE {where_clause}"
            
            result = conn.execute(db.text(query), params)
            row = result.fetchone()
            
            if row:
                loc = Location(
                    id=row[0],
                    name=row[1],
                    status=row[2],
                    webhook_base=row[3],
                    api_key=row[4]
                )
                return loc
            return None
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Error querying location: {e}")
            return None

class Location:
    """Location model replica to avoid circular imports."""
    query = QueryMock(None) # Class attribute to mimic SQLAlchemy query interface
    # Make it compatible with location.py routes file
    __tablename__ = "location"
    
    def __init__(self, id=None, name=None, status="inactive", webhook_base=None, api_key=None):
        self.id = id
        self.name = name
        self.status = status
        self.webhook_base = webhook_base
        self.api_key = api_key
    
    @staticmethod
    def get_from_db(location_id):
        """Get location from database by ID."""
        try:
            conn = db.engine.connect()
            query = "SELECT id, name, status, webhook_base, api_key FROM \"location\" WHERE id = :id"
            result = conn.execute(db.text(query), {"id": location_id})
            row = result.fetchone()
            if row:
                return Location(
                    id=row[0], 
                    name=row[1], 
                    status=row[2], 
                    webhook_base=row[3], 
                    api_key=row[4]
                )
            return None
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Error getting location: {e}")
            return None
    
    def __repr__(self):
        return f"<Location {self.id} - {self.name} - {self.status}>"
        
    def save(self):
        """Save the location to the database."""
        try:
            conn = db.engine.connect()
            if self.id:
                # Update existing record
                query = """
                UPDATE "location" 
                SET name = :name, status = :status, webhook_base = :webhook_base, api_key = :api_key
                WHERE id = :id
                """
                params = {
                    "id": self.id,
                    "name": self.name,
                    "status": self.status,
                    "webhook_base": self.webhook_base,
                    "api_key": self.api_key
                }
                conn.execute(db.text(query), params)
                conn.commit()
            else:
                # Insert new record
                query = """
                INSERT INTO "location" (id, name, status, webhook_base, api_key)
                VALUES (:id, :name, :status, :webhook_base, :api_key)
                """
                params = {
                    "id": self.id,
                    "name": self.name,
                    "status": self.status,
                    "webhook_base": self.webhook_base,
                    "api_key": self.api_key
                }
                conn.execute(db.text(query), params)
                conn.commit()
            return True
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Error saving location: {e}")
            return False

# Set Location.query.model_class to enable filter_by chain
Location.query = QueryMock(Location)