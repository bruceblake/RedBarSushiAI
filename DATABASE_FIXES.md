# Database Fixes and Improvements

This document details the changes made to address several issues with the database schema, model definitions, and JSONB handling in the RedBarSushiAI project.

## Schema-Model Discrepancy

### Issue

A discrepancy was discovered between the database schema and model code:

- **Database Schema**: Column named `snoozed_until` (as per `db/init/01_schema.sql`)
- **Model Code**: Property named `snooze_until` (as used in `app/models/menu.py`)

This inconsistency could lead to errors during database operations and confusion during development.

### Solution

Rather than performing a schema migration (which would be disruptive), we implemented a backward-compatible property-based solution:

```python
# In app/models/menu.py

# Primary attribute matches the database column name
snoozed_until = db.Column(db.DateTime, nullable=True)

# For backwards compatibility - maps to snoozed_until
@property
def snooze_until(self):
    return self.snoozed_until
    
@snooze_until.setter
def snooze_until(self, value):
    self.snoozed_until = value
```

This approach:
1. Preserves the database schema as is
2. Maintains compatibility with existing code referencing `snooze_until`
3. Provides a clear path for future code to use the correct attribute name

### Usage Example

The property allows both attributes to be used interchangeably:

```python
# Both of these work the same way
menu_item.snoozed_until = datetime.now() + timedelta(hours=2)
menu_item.snooze_until = datetime.now() + timedelta(hours=2)

# Both of these return the same value
expiry_time = menu_item.snoozed_until
expiry_time = menu_item.snooze_until
```

## JSONB Serialization Improvements

### Issue

Several models used JSONB fields (stored as the `properties` column) that sometimes contained non-serializable Python objects, leading to database errors when performing write operations.

The most common issues were:
1. Date and datetime objects not being JSON-serializable
2. Custom Python objects with no JSON representation
3. Invalid JSON strings in existing records

### Solution

We implemented a comprehensive sanitization system for JSONB properties:

```python
def sanitize_properties(props):
    """
    Sanitize properties to ensure they are JSON-serializable
    """
    # If None, return empty dict/string based on dialect
    if props is None:
        if is_postgresql():
            return {}
        else:
            return '{}'
    
    # If already a string, validate it's valid JSON
    if isinstance(props, str):
        try:
            # Verify it's valid JSON
            json.loads(props)
            return props
        except json.JSONDecodeError:
            # If invalid JSON string, return empty
            logger.warning("Invalid JSON string in properties, returning empty")
            return '{}' if not is_postgresql() else {}
    
    # For dictionaries, ensure all values are serializable
    if isinstance(props, dict):
        sanitized = {}
        for k, v in props.items():
            # Handle non-serializable types
            if isinstance(v, (datetime, date)):
                sanitized[k] = v.isoformat()
            elif hasattr(v, '__dict__'):  # Handle custom objects
                sanitized[k] = str(v)
            elif v is None or isinstance(v, (str, int, float, bool, list, dict)):
                sanitized[k] = v
            else:
                # For other types, convert to string
                sanitized[k] = str(v)
        return sanitized
    
    # For other types, convert to string representation
    return str(props)
```

This was integrated into model methods:

```python
def to_dict(self):
    """Convert model to dictionary with sanitized properties"""
    result = {
        'id': self.id,
        'name': self.name,
        # ... other fields
    }
    
    # Sanitize properties before adding to dict
    if hasattr(self, 'properties'):
        result['properties'] = sanitize_properties(self.properties)
    
    return result
```

### Benefits

The sanitization system:
1. Prevents errors when saving objects with datetime fields
2. Handles nested non-serializable objects
3. Recovers from invalid JSON data
4. Provides detailed logging for troubleshooting
5. Maintains backward compatibility with existing code

## Error Handling and Recovery

### Issues

Several potential failure points in database operations were identified:
1. Database connection failures
2. Serialization errors
3. Invalid data in existing records
4. Cache inconsistencies between Redis and the database

### Solutions

We implemented multi-level error handling and recovery:

```python
def _get_menu_item_by_plu(self, plu):
    """Get a menu item by PLU with error handling and fallbacks"""
    try:
        # First try the cache for performance
        cached_item = self._get_from_cache(f"menu_item:{plu}")
        if cached_item:
            return cached_item
    except Exception as cache_e:
        logger.warning(f"Cache error retrieving menu item with PLU {plu}: {str(cache_e)}")
        # Fall through to database retrieval
    
    try:
        # Attempt to get from database
        item = MenuItem.query.filter_by(plu=plu).first()
        if item:
            # Update cache for future requests
            self._update_cache(f"menu_item:{plu}", item)
            return item
    except Exception as db_e:
        logger.error(f"Database error retrieving menu item with PLU {plu}: {str(db_e)}")
        # No fallback, return None and let caller handle
        return None
```

For JSONB operations, we added multi-level validation:

```python
def _load_properties(self, properties_value):
    """Safely load JSONB properties with validation and error handling"""
    if properties_value is None:
        return {}
        
    if isinstance(properties_value, dict):
        return properties_value
        
    try:
        # If it's a string (SQLite), parse it
        if isinstance(properties_value, str):
            return json.loads(properties_value)
        # For PostgreSQL JSONB, it should already be a dict
        return properties_value
    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode JSONB properties: {e}")
        # Return empty dict as fallback
        return {}
    except Exception as e:
        logger.error(f"Unexpected error processing properties: {e}")
        return {}
```

### Integration Points

These error handling improvements were integrated into:

1. `app/models/menu.py`: Added property handling and model serialization
2. `app/models/base.py`: Added base model improvements for all models
3. `app/utils/menu_db_store.py`: Enhanced database operations with proper error handling
4. `app/utils/menu_cache_sdk.py`: Added cache reliability improvements

### Monitoring and Diagnostics

We also added improved logging to help diagnose database issues:

```python
def _handle_db_operation(self, operation_name, func, *args, **kwargs):
    """
    Wrapper to handle database operations with proper logging and error handling
    """
    start_time = time.time()
    try:
        result = func(*args, **kwargs)
        duration = time.time() - start_time
        logger.debug(f"DB operation '{operation_name}' completed in {duration:.3f}s")
        return result
    except SQLAlchemyError as e:
        duration = time.time() - start_time
        logger.error(f"DB operation '{operation_name}' failed after {duration:.3f}s: {str(e)}")
        # Optionally report metrics or trigger alerts
        raise
```

## Conclusion

These database improvements collectively enhance the stability and reliability of the RedBarSushiAI system by:

1. **Ensuring Schema-Model Alignment**: Eliminating discrepancies between database schema and model code
2. **Improving JSONB Handling**: Preventing serialization errors that could cause database operations to fail
3. **Enhancing Error Recovery**: Adding multi-level fallbacks and validation to recover from various error conditions
4. **Adding Observability**: Providing detailed logging to diagnose and troubleshoot database issues

These changes maintain backward compatibility while improving system resilience, making the application more robust against various failure modes.