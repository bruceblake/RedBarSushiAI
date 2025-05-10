# RedBarSushiAI Refactoring Notes

## Order Routes Refactoring

### Flask to FastAPI Conversion

The original monolithic `app/routes/order.py` file has been refactored in two phases:

1. **Phase 1:** Breaking down the Flask Blueprint-based code into smaller modules in `app/routes/order/`:

   - `__init__.py`: Router registration and exports
   - `status.py`: Order status routes
   - `take_order.py`: Order creation routes
   - `confirmation.py`: Order confirmation routes
   - `checkout.py`: Order checkout routes
   - `modification.py`: Order modification routes
   - `contact.py`: Contact-related routes
   - `utils.py`: Shared utility functions

2. **Phase 2:** Converting Flask Blueprint modules to FastAPI Routers in `app/api/order/`:
   - Each module in `app/routes/order/` has a corresponding FastAPI version in `app/api/order/`
   - Routes are converted from Flask-style (`@blueprint.route()`) to FastAPI-style (`@router.get()`, `@router.post()`)
   - Synchronous functions are converted to async (`async def`)
   - Request handling is converted from Flask's request object to FastAPI's dependency injection and Pydantic models
   - Response generation is converted from Flask's Response objects to FastAPI's return values and response models

### Key Changes

#### Database Access

- Replaced Flask-SQLAlchemy with SQLAlchemy 2.0 async
- Created async models in `app/models/order_async.py` with properly typed Mapped columns
- Added dependency injection for database sessions (`db: AsyncSession = Depends(get_db)`)
- Converted CRUD operations to use async/await pattern

#### Request Handling

- Replaced Flask's `request.form`, `request.json` with Pydantic models
- Added proper type annotations and validation
- Implemented proper error handling with HTTPException

#### Response Generation

- Replaced Flask's `jsonify()` and `Response()` with Pydantic response models
- Standardized error responses
- Added proper status codes

### Async Utilities

- Created async versions of helper functions in `app/utils/helpers_async.py`:
  - `commit_with_retry_async`: Async version of the transaction commit with retry
  - `log_info_async`: Async wrapper for logging
  - `get_common_prices_async`: Async version of menu price retrieval

### Router Integration

- Updated `app/api/__init__.py` to include the new order routers
- Routes are accessible at `/order/...` prefix

## Testing Considerations

- Both sets of routes (Flask and FastAPI) can coexist during the transition
- Gradually migrate API consumers to the new FastAPI endpoints
- Once all consumers are migrated, the Flask routes can be removed

## Next Steps

1. Complete the conversion of all modules in `app/routes/order/` to FastAPI
2. Add comprehensive tests for the new FastAPI routes
3. Update documentation and API references
4. Gradually phase out the Flask routes
