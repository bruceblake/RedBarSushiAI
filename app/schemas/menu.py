"""
Pydantic schemas for menu-related operations.

This module provides request/response schemas for menu API endpoints,
based on Deliverect webhook format.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# Deliverect-compatible base schemas
class DeliverectAvailability(BaseModel):
    dayOfWeek: int
    startTime: str
    endTime: str


class DeliverectProduct(BaseModel):
    _id: str
    name: str
    description: Optional[str] = ""
    descriptionTranslations: Optional[Dict[str, str]] = {}
    nameTranslations: Optional[Dict[str, str]] = {}
    account: str
    capacityUsages: Optional[List] = []
    deliveryTax: Optional[int] = 0
    eatInTax: Optional[int] = 0
    takeawayTax: Optional[int] = 0
    imageUrl: Optional[str] = ""
    location: str
    max: int = 0
    min: int = 0
    multiply: int = 1
    plu: str
    posCategoryIds: Optional[List] = []
    posProductCategoryId: Optional[str] = ""
    posProductId: Optional[str] = ""
    price: int  # Price in cents
    productTags: Optional[List] = []
    productType: int  # 1=product, 2=modifier, 3=modifier group
    subProducts: Optional[List[str]] = []
    parentId: Optional[str] = None
    snoozed: bool = False
    subProductSortOrder: Optional[List] = []
    referenceId: Optional[str] = None


class DeliverectCategory(BaseModel):
    _id: str
    name: str
    description: Optional[str] = ""
    descriptionTranslations: Optional[Dict[str, str]] = {}
    nameTranslations: Optional[Dict[str, str]] = {}
    account: str
    posLocationId: Optional[str] = ""
    posCategoryType: Optional[str] = ""
    posCategoryId: Optional[str] = ""
    imageUrl: Optional[str] = ""
    subCategories: Optional[List] = []
    products: Optional[List] = []
    availabilities: Optional[List] = []
    level: int = 1
    menu: str
    sortedChannelProductIds: Optional[List] = []
    subProducts: Optional[List[str]] = []
    subProductSortOrder: Optional[List] = []


class DeliverectMenu(BaseModel):
    availabilities: Optional[List[DeliverectAvailability]] = []
    bundles: Optional[Dict] = {}
    categories: List[DeliverectCategory] = []
    channelLinkId: str
    currency: int
    description: Optional[str] = ""
    descriptionTranslations: Optional[Dict[str, str]] = {}
    menu: str
    menuId: str
    menuImageURL: Optional[str] = ""
    menuType: int = 0
    modifierGroups: Optional[Dict[str, DeliverectProduct]] = {}
    modifiers: Optional[Dict[str, DeliverectProduct]] = {}
    menuTranslations: Optional[Dict[str, str]] = {}
    nestedModifiers: bool = True
    products: Optional[Dict[str, DeliverectProduct]] = {}
    productTags: Optional[List[int]] = []
    snoozedProducts: Optional[Dict] = {}
    validations: Optional[List] = []


# Internal database schemas (for our local storage)
class MenuCategoryBase(BaseModel):
    name: str
    description: Optional[str] = None
    display_order: int = 0
    is_available: bool = True


class MenuCategoryCreate(MenuCategoryBase):
    pass


class MenuCategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    display_order: Optional[int] = None
    is_available: Optional[bool] = None


class MenuItemBase(BaseModel):
    name: str
    description: Optional[str] = None
    price: int  # Price in cents
    plu: str
    category_id: int
    is_available: bool = True
    image_url: Optional[str] = None


class MenuItemCreate(MenuItemBase):
    pass


class MenuItemUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[int] = None
    plu: Optional[str] = None
    category_id: Optional[int] = None
    is_available: Optional[bool] = None
    image_url: Optional[str] = None


class MenuModifierBase(BaseModel):
    name: str
    description: Optional[str] = None
    price_change: int = 0  # Price change in cents
    plu: str
    is_available: bool = True


class MenuModifierCreate(MenuModifierBase):
    pass


class MenuModifierUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price_change: Optional[int] = None
    plu: Optional[str] = None
    is_available: Optional[bool] = None


class MenuModifierGroupBase(BaseModel):
    name: str
    description: Optional[str] = None
    min_selection: int = 0
    max_selection: Optional[int] = None
    is_required: bool = False


class MenuModifierGroupCreate(MenuModifierGroupBase):
    pass


class MenuModifierGroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    min_selection: Optional[int] = None
    max_selection: Optional[int] = None
    is_required: Optional[bool] = None


class MenuVariantBase(BaseModel):
    variant_name: str
    plu: str


class MenuVariantCreate(MenuVariantBase):
    pass


class MenuVariantUpdate(BaseModel):
    variant_name: Optional[str] = None
    plu: Optional[str] = None


# Response schemas for API endpoints
class MenuCategoryResponse(MenuCategoryBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class MenuCategoryListResponse(BaseModel):
    categories: List[MenuCategoryResponse]
    total: int
    page: int
    per_page: int


class MenuItemResponse(MenuItemBase):
    id: int
    created_at: datetime
    updated_at: datetime
    category: Optional[MenuCategoryResponse] = None
    
    class Config:
        from_attributes = True


class MenuItemListResponse(BaseModel):
    items: List[MenuItemResponse]
    total: int
    page: int
    per_page: int


class MenuModifierResponse(MenuModifierBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class MenuModifierGroupResponse(MenuModifierGroupBase):
    id: int
    modifiers: List[MenuModifierResponse] = []
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class MenuModifierListResponse(BaseModel):
    modifiers: List[MenuModifierResponse]
    total: int
    page: int
    per_page: int


class MenuModifierGroupListResponse(BaseModel):
    groups: List[MenuModifierGroupResponse]
    total: int
    page: int
    per_page: int


class MenuVariantResponse(MenuVariantBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class MenuVariantListResponse(BaseModel):
    variants: List[MenuVariantResponse]
    total: int
    page: int
    per_page: int


# Snooze-related schemas
class SnoozeRequest(BaseModel):
    duration_minutes: int = Field(..., ge=1, le=1440, description="Snooze duration in minutes (1-1440)")
    reason: Optional[str] = Field(None, description="Reason for snoozing the item")


class SnoozeResponse(BaseModel):
    success: bool
    message: str
    snoozed_until: Optional[datetime] = None
    item_id: int
    item_name: str


# Webhook schemas for receiving Deliverect data
class MenuWebhookPayload(BaseModel):
    """Schema for incoming Deliverect menu webhook payload"""
    payload: List[DeliverectMenu]
    
    
class MenuSyncResponse(BaseModel):
    """Response after processing menu webhook"""
    success: bool
    message: str
    items_processed: int
    categories_processed: int
    modifiers_processed: int