# Deliverect Webhook Implementation Plan

## Overview

This document outlines the plan for implementing the Deliverect webhook endpoint for menu updates. This is a critical component that receives menu updates from Deliverect and processes them to update our internal menu database.

## Current Understanding

The Deliverect webhook is the primary mechanism for updating the menu in our system:

1. Deliverect sends a POST request to our webhook endpoint (`/menu_update` or `/deliverect/menu`)
2. The request contains a JSON payload with the entire menu structure
3. Our system processes this payload, transforming it into our internal data model
4. The processed data is stored in our PostgreSQL database
5. After successful database update, the Redis cache is invalidated or updated
6. A confirmation is sent back to Deliverect with status "ONLINE" or "FAILED"

## Implementation Plan

### 1. Define Pydantic Models for Deliverect Payload

Create models based on the Deliverect menu push schema (as per https://developers.deliverect.com/reference/post-menu-push):

```python
class DeliverectCategory(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    # Additional fields as per Deliverect schema

class DeliverectItem(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    price: float
    plu: Optional[str] = None
    # Additional fields as per Deliverect schema

class DeliverectModifier(BaseModel):
    id: str
    name: str
    price: float
    plu: Optional[str] = None
    # Additional fields as per Deliverect schema

class DeliverectModifierGroup(BaseModel):
    id: str
    name: str
    min_selection: int
    max_selection: int
    # Additional fields as per Deliverect schema

class DeliverectMenu(BaseModel):
    categories: List[DeliverectCategory]
    items: List[DeliverectItem]
    # Additional fields as per Deliverect schema

class DeliverectMenuPushRequest(BaseModel):
    menu: DeliverectMenu
    account_id: str
    channel_id: str
    callback_url: Optional[str] = None
    # Additional fields as per Deliverect schema
```

### 2. Create the FastAPI Endpoint

Create a dedicated FastAPI module for handling Deliverect webhooks:

```python
@router.post("/menu_update", status_code=status.HTTP_200_OK)
async def update_menu_from_deliverect(
    payload: DeliverectMenuPushRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Process menu update from Deliverect.
    
    This endpoint receives a menu update from Deliverect and processes it
    to update our internal menu database.
    """
    try:
        # Process the Deliverect menu data
        processed_data = await process_deliverect_menu(payload.menu)
        
        # Validate and fix the menu data
        validated_data = await validate_and_fix_menu_data(processed_data)
        
        # Store the data in the database
        location_id = get_location_id_from_channel(payload.channel_id)
        await store_menu_data(db, validated_data, location_id)
        
        # Invalidate or update Redis cache
        background_tasks.add_task(update_menu_cache, location_id)
        
        # Send confirmation back to Deliverect if callback_url is provided
        if payload.callback_url:
            background_tasks.add_task(
                send_callback_to_deliverect, 
                payload.callback_url, 
                status="ONLINE"
            )
        
        return {"status": "success", "message": "Menu updated successfully"}
        
    except Exception as e:
        # Log the error
        logger.error(f"Error processing menu update: {str(e)}")
        
        # Send failure notification back to Deliverect if callback_url is provided
        if payload.callback_url:
            background_tasks.add_task(
                send_callback_to_deliverect, 
                payload.callback_url, 
                status="FAILED"
            )
        
        # Re-raise the exception to return appropriate HTTP error
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing menu update: {str(e)}"
        )
```

### 3. Implement Helper Functions

Port and adapt the helper functions from the original Flask route:

#### a. Process Deliverect Menu

```python
async def process_deliverect_menu(menu_data: DeliverectMenu) -> Dict[str, Any]:
    """
    Process the Deliverect menu data and transform it to our internal data structure.
    """
    # Convert Deliverect categories to our internal format
    # Convert Deliverect items to our internal format
    # Convert Deliverect modifiers to our internal format
    # Map relationships between items, categories, modifiers, etc.
    # Return the processed data
```

#### b. Validate and Fix Menu Data

```python
async def validate_and_fix_menu_data(menu_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and fix menu data to ensure it's consistent and ready for database storage.
    """
    # Check for required fields
    # Fix inconsistencies
    # Handle special cases
    # Return the validated data
```

#### c. Store Menu Data

```python
async def store_menu_data(
    db: AsyncSession, menu_data: Dict[str, Any], location_id: str
) -> None:
    """
    Store the processed menu data in the database.
    """
    # Create a database transaction
    # Clear existing menu data for the location (optional, depends on approach)
    # Create categories
    # Create items
    # Create modifiers and modifier groups
    # Establish relationships
    # Commit the transaction
```

#### d. Update Menu Cache

```python
async def update_menu_cache(location_id: str) -> None:
    """
    Update the Redis cache after a successful database update.
    """
    # Invalidate relevant cache keys
    # Or refresh the cache with the latest data
```

#### e. Send Callback to Deliverect

```python
async def send_callback_to_deliverect(callback_url: str, status: str) -> None:
    """
    Send confirmation back to Deliverect.
    """
    # Use httpx.AsyncClient to make an async HTTP request
    # Send appropriate status and any required data
    # Handle success/failure of the callback
```

### 4. Integration with Existing System

- Update app/api/menu/__init__.py to include the new update router
- Ensure the webhook endpoint is properly registered and accessible
- Add error handling and logging
- Add appropriate authentication/authorization if required
- Test the implementation with sample Deliverect payloads

### 5. Testing Strategy

1. **Unit Tests**:
   - Test processing functions with sample Deliverect payloads
   - Test database storage with mock data
   - Test error handling and validation logic

2. **Integration Tests**:
   - Test the complete flow from webhook to database and cache
   - Test callback functionality with mock Deliverect endpoint

3. **Manual Testing**:
   - Test with actual Deliverect test accounts if available
   - Test with sample payloads from actual Deliverect pushes

## Questions to Resolve

1. Should we clear all existing menu data for a location before inserting new data, or perform upserts?
2. How should we handle menu items that are present in our database but not in the Deliverect payload?
3. What validation and cleaning steps are required for the Deliverect payload?
4. How should we handle failures during the processing/storage of the menu data?
5. What Redis cache keys need to be invalidated/updated after a menu update?

## Next Steps

1. Review existing code in app/routes/menu.py related to Deliverect webhook handling
2. Understand the current validation and transformation logic
3. Define Pydantic models based on actual Deliverect payloads
4. Implement the FastAPI endpoint with proper async operations
5. Test with sample payloads before deploying