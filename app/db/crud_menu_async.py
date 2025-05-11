# Variant CRUD operations
async def get_variants(
    db: AsyncSession, 
    skip: int = 0, 
    limit: int = 100,
    target_plu: Optional[str] = None,
    canonical_name: Optional[str] = None
) -> List[MenuNameVariant]:
    """
    Get all menu name variants with pagination and optional filtering.
    
    Args:
        db: Database session
        skip: Number of records to skip
        limit: Maximum number of records to return
        target_plu: Optional PLU to filter by
        canonical_name: Optional canonical name to filter by
        
    Returns:
        List of MenuNameVariant objects
    """
    query = select(MenuNameVariant).offset(skip).limit(limit).order_by(MenuNameVariant.variant_phrase)
    
    # Add filters if provided
    if target_plu:
        query = query.where(MenuNameVariant.target_plu == target_plu)
        
    if canonical_name:
        query = query.where(MenuNameVariant.canonical_name == canonical_name)
        
    result = await db.execute(query)
    return list(result.scalars().all())

async def count_variants(
    db: AsyncSession,
    target_plu: Optional[str] = None,
    canonical_name: Optional[str] = None
) -> int:
    """
    Count all menu name variants with optional filtering.
    
    Args:
        db: Database session
        target_plu: Optional PLU to filter by
        canonical_name: Optional canonical name to filter by
        
    Returns:
        Total count of variants
    """
    query = select(func.count()).select_from(MenuNameVariant)
    
    # Add filters if provided
    if target_plu:
        query = query.where(MenuNameVariant.target_plu == target_plu)
        
    if canonical_name:
        query = query.where(MenuNameVariant.canonical_name == canonical_name)
        
    result = await db.execute(query)
    return result.scalar_one()

async def get_variant(db: AsyncSession, variant_id: str) -> Optional[MenuNameVariant]:
    """
    Get a specific menu name variant by ID.
    
    Args:
        db: Database session
        variant_id: Variant ID to retrieve
        
    Returns:
        MenuNameVariant object or None if not found
    """
    query = select(MenuNameVariant).where(MenuNameVariant.id == variant_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()

async def get_variant_by_phrase(
    db: AsyncSession, variant_phrase: str
) -> Optional[MenuNameVariant]:
    """
    Get a specific menu name variant by phrase.
    
    Args:
        db: Database session
        variant_phrase: Variant phrase to retrieve
        
    Returns:
        MenuNameVariant object or None if not found
    """
    # Convert to lowercase for case-insensitive comparison
    phrase = variant_phrase.lower()
    query = select(MenuNameVariant).where(func.lower(MenuNameVariant.variant_phrase) == phrase)
    result = await db.execute(query)
    return result.scalar_one_or_none()

async def create_variant(db: AsyncSession, variant: MenuVariantCreate) -> MenuNameVariant:
    """
    Create a new menu name variant.
    
    Args:
        db: Database session
        variant: Variant data to create
        
    Returns:
        Created MenuNameVariant object
    """
    db_variant = MenuNameVariant(
        variant_phrase=variant.variant_phrase,
        canonical_name=variant.canonical_name,
        target_plu=variant.target_plu
    )
    db.add(db_variant)
    await db.commit()
    await db.refresh(db_variant)
    return db_variant

async def update_variant(
    db: AsyncSession, variant_id: str, variant: MenuVariantUpdate
) -> Optional[MenuNameVariant]:
    """
    Update an existing menu name variant.
    
    Args:
        db: Database session
        variant_id: ID of variant to update
        variant: Updated variant data
        
    Returns:
        Updated MenuNameVariant object or None if not found
    """
    # Get the variant
    db_variant = await get_variant(db, variant_id)
    if not db_variant:
        return None
        
    # Update attributes that are provided
    update_data = variant.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_variant, key, value)
        
    # Commit the changes
    await db.commit()
    await db.refresh(db_variant)
    return db_variant

async def delete_variant(db: AsyncSession, variant_id: str) -> bool:
    """
    Delete a menu name variant.
    
    Args:
        db: Database session
        variant_id: ID of variant to delete
        
    Returns:
        True if deleted, False if not found
    """
    # Get the variant
    db_variant = await get_variant(db, variant_id)
    if not db_variant:
        return False
        
    # Delete the variant
    await db.delete(db_variant)
    await db.commit()
    return True