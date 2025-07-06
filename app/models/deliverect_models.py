"""
Pydantic models for Deliverect API data structures.

These models represent the exact structure of data returned from the Deliverect API,
providing type safety and validation for menu synchronization and caching.
They complement the existing SQLAlchemy models by providing a direct representation
of Deliverect's data format before transformation to our database schema.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class Modifier(BaseModel):
    """
    Represents a single modifier option from Deliverect.
    
    Example: "Extra Wasabi" (+$0.50) or "No Rice" (+$0.00)
    """
    id: str = Field(..., alias='_id')
    plu: str
    name: str
    price: int = Field(..., description="Price in cents")
    product_type: int = Field(..., alias='productType')
    snoozed: bool = False
    
    class Config:
        allow_population_by_field_name = True


class ModifierGroup(BaseModel):
    """
    Represents a group of modifiers from Deliverect.
    
    Example: "Spice Level" (min: 1, max: 1) containing ["Mild", "Medium", "Hot"]
    """
    id: str = Field(..., alias='_id')
    plu: str
    name: str
    min_selection: int = Field(..., alias='min', description="Minimum required selections")
    max_selection: int = Field(..., alias='max', description="Maximum allowed selections")
    multi_max: int = Field(..., alias='multiMax', description="Maximum quantity per modifier")
    sub_products: List[str] = Field(..., alias='subProducts', description="List of Modifier PLUs")
    is_variant_group: bool = Field(False, alias='isVariantGroup')
    snoozed: bool = False
    
    class Config:
        allow_population_by_field_name = True


class Product(BaseModel):
    """
    Represents a menu item from Deliverect.
    
    Example: "California Roll" with associated modifier groups for customization
    """
    id: str = Field(..., alias='_id')
    plu: str
    name: str
    description: Optional[str] = ""
    price: int = Field(..., description="Price in cents")
    product_type: int = Field(..., alias='productType')
    sub_products: List[str] = Field([], alias='subProducts', description="List of ModifierGroup PLUs")
    snoozed: bool = False
    is_variant: bool = Field(False, alias='isVariant')
    product_tags: List[int] = Field([], alias='productTags', description="Category/allergen tags")
    
    class Config:
        allow_population_by_field_name = True


class DeliverectMenu(BaseModel):
    """
    Complete menu structure from Deliverect API.
    
    This represents the full menu payload including all products, modifiers,
    modifier groups, and snoozed item tracking.
    """
    products: Dict[str, Product] = Field(default_factory=dict, description="Products indexed by PLU")
    modifiers: Dict[str, Modifier] = Field(default_factory=dict, description="Modifiers indexed by PLU")
    modifier_groups: Dict[str, ModifierGroup] = Field(
        default_factory=dict, 
        alias='modifierGroups',
        description="Modifier groups indexed by PLU"
    )
    snoozed_products: List[str] = Field(
        default_factory=list,
        alias='snoozedProducts', 
        description="List of PLUs that are currently unavailable"
    )
    
    class Config:
        allow_population_by_field_name = True


class MenuLookupResult(BaseModel):
    """
    Structured result from menu item lookup operations.
    
    This is returned by the enhanced MenuAgent tools to provide comprehensive
    information about a matched item including all customization options.
    """
    found: bool
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="Match confidence score")
    item: Optional[Product] = None
    modifier_groups: List[ModifierGroup] = Field(default_factory=list)
    modifiers: Dict[str, Modifier] = Field(default_factory=dict, description="Available modifiers keyed by PLU")
    suggested_alternatives: List[Product] = Field(default_factory=list, description="Alternative items if no exact match")
    
    @property
    def has_required_modifiers(self) -> bool:
        """Check if the item has any modifier groups that require selection."""
        return any(group.min_selection > 0 for group in self.modifier_groups)
    
    @property
    def required_modifier_groups(self) -> List[ModifierGroup]:
        """Get only the modifier groups that require selection."""
        return [group for group in self.modifier_groups if group.min_selection > 0]


class ItemAvailabilityStatus(BaseModel):
    """
    Status information for item availability checking.
    """
    plu: str
    name: str
    is_available: bool
    snoozed: bool
    reason: Optional[str] = None  # Why item is unavailable
    estimated_available_time: Optional[str] = None  # When it might be available again


class MenuCacheMetadata(BaseModel):
    """
    Metadata for menu cache management.
    """
    last_updated: str  # ISO timestamp
    cache_version: str
    total_products: int
    total_modifiers: int
    total_modifier_groups: int
    snoozed_count: int