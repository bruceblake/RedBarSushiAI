"""
Pydantic models for menu-related data.

These models define the schemas for input and output data related to
menu categories, items, modifiers, and variants.
"""

from typing import List, Dict, Any, Optional, Union
from datetime import datetime
from pydantic import BaseModel, Field, validator, root_validator


class MenuCategoryBase(BaseModel):
    """Base model for menu categories."""
    name: str
    description: Optional[str] = None
    deliverect_category_id: Optional[str] = None


class MenuCategoryCreate(MenuCategoryBase):
    """Model for creating a new menu category."""
    pass


class MenuCategoryUpdate(BaseModel):
    """Model for updating a menu category."""
    name: Optional[str] = None
    description: Optional[str] = None
    deliverect_category_id: Optional[str] = None


class MenuCategoryResponse(MenuCategoryBase):
    """Model for menu category response."""
    id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        orm_mode = True


class MenuCategoryListResponse(BaseModel):
    """Model for a list of menu categories."""
    categories: List[MenuCategoryResponse]
    total: int


class MenuItemBase(BaseModel):
    """Base model for menu items."""
    name: str
    description: Optional[str] = None
    price: float = 0.0
    plu: Optional[str] = None
    deliverect_item_id: Optional[str] = None
    is_available: bool = True
    is_combo: bool = False
    is_variant: bool = False
    image_url: Optional[str] = None
    category_id: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None


class MenuItemCreate(MenuItemBase):
    """Model for creating a new menu item."""
    pass


class MenuItemUpdate(BaseModel):
    """Model for updating a menu item."""
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    plu: Optional[str] = None
    deliverect_item_id: Optional[str] = None
    is_available: Optional[bool] = None
    is_combo: Optional[bool] = None
    is_variant: Optional[bool] = None
    image_url: Optional[str] = None
    category_id: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None


class MenuItemResponse(MenuItemBase):
    """Model for menu item response."""
    id: str
    snoozed_until: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        orm_mode = True


class MenuItemListResponse(BaseModel):
    """Model for a list of menu items."""
    items: List[MenuItemResponse]
    total: int


class MenuModifierBase(BaseModel):
    """Base model for menu modifiers."""
    name: str
    price_change: float = 0.0
    plu: Optional[str] = None
    deliverect_modifier_id: Optional[str] = None
    is_available: bool = True
    modifier_group_id: Optional[str] = None


class MenuModifierCreate(MenuModifierBase):
    """Model for creating a new menu modifier."""
    pass


class MenuModifierUpdate(BaseModel):
    """Model for updating a menu modifier."""
    name: Optional[str] = None
    price_change: Optional[float] = None
    plu: Optional[str] = None
    deliverect_modifier_id: Optional[str] = None
    is_available: Optional[bool] = None
    modifier_group_id: Optional[str] = None


class MenuModifierResponse(MenuModifierBase):
    """Model for menu modifier response."""
    id: str
    snoozed_until: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        orm_mode = True


class MenuModifierListResponse(BaseModel):
    """Model for a list of menu modifiers."""
    modifiers: List[MenuModifierResponse]
    total: int


class MenuModifierGroupBase(BaseModel):
    """Base model for menu modifier groups."""
    name: str
    min_selection: int = 0
    max_selection: int = 1
    multi_max: Optional[int] = None
    plu: Optional[str] = None
    is_variant_group: bool = False
    deliverect_group_id: Optional[str] = None


class MenuModifierGroupCreate(MenuModifierGroupBase):
    """Model for creating a new menu modifier group."""
    pass


class MenuModifierGroupUpdate(BaseModel):
    """Model for updating a menu modifier group."""
    name: Optional[str] = None
    min_selection: Optional[int] = None
    max_selection: Optional[int] = None
    multi_max: Optional[int] = None
    plu: Optional[str] = None
    is_variant_group: Optional[bool] = None
    deliverect_group_id: Optional[str] = None


class MenuModifierGroupResponse(MenuModifierGroupBase):
    """Model for menu modifier group response."""
    id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    modifiers: Optional[List[MenuModifierResponse]] = None
    
    class Config:
        orm_mode = True


class MenuModifierGroupListResponse(BaseModel):
    """Model for a list of menu modifier groups."""
    modifier_groups: List[MenuModifierGroupResponse]
    total: int


class MenuVariantBase(BaseModel):
    """Base model for menu name variants."""
    variant_phrase: str
    canonical_name: str
    target_plu: Optional[str] = None


class MenuVariantCreate(MenuVariantBase):
    """Model for creating a new menu name variant."""
    pass


class MenuVariantUpdate(BaseModel):
    """Model for updating a menu name variant."""
    variant_phrase: Optional[str] = None
    canonical_name: Optional[str] = None
    target_plu: Optional[str] = None


class MenuVariantResponse(MenuVariantBase):
    """Model for menu name variant response."""
    id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        orm_mode = True


class MenuVariantListResponse(BaseModel):
    """Model for a list of menu name variants."""
    variants: List[MenuVariantResponse]
    total: int


class SnoozeRequest(BaseModel):
    """Model for snoozing or unsnoozing an item."""
    item_id: str
    snooze: bool = True
    duration_minutes: Optional[int] = 60  # Default to 1 hour
    
    @validator('duration_minutes')
    def duration_must_be_positive(cls, v):
        if v is not None and v <= 0:
            raise ValueError('Duration must be positive')
        return v


class SnoozeResponse(BaseModel):
    """Model for snooze/unsnooze response."""
    item_id: str
    name: str
    snoozed: bool
    snoozed_until: Optional[datetime] = None
    message: str