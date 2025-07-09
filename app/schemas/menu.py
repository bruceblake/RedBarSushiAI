"""
Pydantic schemas for menu-related operations.

This module provides request/response schemas for menu API endpoints,
based on Deliverect webhook format.

IMPORTANT SCHEMA UPDATES (Fixed for production):
1. Changed price fields from int to float to handle decimal prices (e.g., 0.5)
2. Changed tax fields from int to float to handle tax rates (e.g., 20.0)
3. Added comprehensive optional fields found in real Deliverect menu data
4. Added flexible webhook schemas with custom validators for robust data handling
5. Added extra="allow" config to handle new fields Deliverect might add
6. Added validator functions to safely convert string/int values to float

These changes prevent validation errors like:
- "Input should be a valid integer, got a number with a fractional part"
- Missing field errors for new Deliverect fields
- Type conversion errors for price/tax values
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator


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
    deliveryTax: Optional[float] = 0.0  # Changed to float for tax rates
    eatInTax: Optional[float] = 0.0  # Changed to float for tax rates
    takeawayTax: Optional[float] = 0.0  # Changed to float for tax rates
    imageUrl: Optional[str] = ""
    location: str
    max: int = 0
    min: int = 0
    multiply: int = 1
    plu: str
    posCategoryIds: Optional[List] = []
    posProductCategoryId: Optional[str] = ""
    posProductId: Optional[str] = ""
    price: float  # Changed to float for decimal prices
    productTags: Optional[List] = []
    productType: int  # 1=product, 2=modifier, 3=modifier group
    subProducts: Optional[List[str]] = []
    parentId: Optional[str] = None
    snoozed: bool = False
    subProductSortOrder: Optional[List] = []
    referenceId: Optional[str] = None
    # New fields found in Deliverect example
    available: Optional[bool] = True
    capacityUsage: Optional[float] = 0.0
    excludeFromAutomaticDiscounts: Optional[bool] = False
    excludeFromChannelDiscounts: Optional[bool] = False
    excludeFromLocationDiscounts: Optional[bool] = False
    excludeFromPlatformDiscounts: Optional[bool] = False
    excludeFromPlatformPromotions: Optional[bool] = False
    hasAvailabilityRules: Optional[bool] = False
    hasOptionGroups: Optional[bool] = False
    hasVariants: Optional[bool] = False
    isFromBundle: Optional[bool] = False
    isParentProduct: Optional[bool] = False
    isVariantProduct: Optional[bool] = False
    hasModifierGroups: Optional[bool] = False
    optionGroups: Optional[List] = []
    position: Optional[int] = 0
    snoozedUntil: Optional[str] = None
    subProductPositions: Optional[List] = []
    totalVariants: Optional[int] = 0
    variants: Optional[List] = []
    visibility: Optional[str] = "VISIBLE"
    weightUnit: Optional[str] = "g"
    averagePreparationTimeInMinutes: Optional[int] = 0
    modifierGroups: Optional[List[str]] = []


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
    # New fields found in Deliverect example
    available: Optional[bool] = True
    channelProductIds: Optional[List] = []
    channelProductIdsNotOverridden: Optional[List] = []
    hasAvailabilityRules: Optional[bool] = False
    hasSubCategories: Optional[bool] = False
    location: Optional[str] = ""
    position: Optional[int] = 0
    snoozedUntil: Optional[str] = None
    sortedChannelProductIdsNotOverridden: Optional[List] = []
    visibility: Optional[str] = "VISIBLE"


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
    # New fields found in Deliverect example
    account: Optional[str] = ""
    activeChannelLinkId: Optional[str] = ""
    # bundles field already exists above
    currency: Optional[int] = 826  # GBP currency code
    globalProductTags: Optional[List[int]] = []
    hasAvailabilities: Optional[bool] = False
    hasCategories: Optional[bool] = True
    hasModifierGroups: Optional[bool] = False
    hasModifiers: Optional[bool] = False
    hasProducts: Optional[bool] = True
    hasProductTags: Optional[bool] = False
    hasValidations: Optional[bool] = False
    lastChangeDate: Optional[str] = ""
    location: Optional[str] = ""
    menuName: Optional[str] = ""
    modifierGroupCount: Optional[int] = 0
    modifierCount: Optional[int] = 0
    name: Optional[str] = ""
    nameTranslations: Optional[Dict[str, str]] = {}
    productCount: Optional[int] = 0
    sortedChannelProductIds: Optional[List] = []
    status: Optional[str] = "ACTIVE"
    totalCategories: Optional[int] = 0
    totalProducts: Optional[int] = 0
    updatedAt: Optional[str] = ""
    version: Optional[int] = 1


# Internal database schemas (for our local storage)
class MenuCategoryBase(BaseModel):
    name: str
    description: Optional[str] = None
    order_index: int = 0  # Changed from display_order to match model
    deliverect_category_id: Optional[str] = None  # Added missing field
    location_id: Optional[str] = None  # Added missing field
    parent_id: Optional[int] = None  # Added missing field
    properties: Optional[Dict[str, Any]] = None  # Added missing field


class MenuCategoryCreate(MenuCategoryBase):
    pass


class MenuCategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    order_index: Optional[int] = None  # Changed from display_order
    deliverect_category_id: Optional[str] = None  # Added missing field
    location_id: Optional[str] = None  # Added missing field
    parent_id: Optional[int] = None  # Added missing field
    properties: Optional[Dict[str, Any]] = None  # Added missing field


class MenuItemBase(BaseModel):
    name: str
    description: Optional[str] = None
    price: float  # Price (can be decimal)  
    plu: Optional[str] = None  # Changed to optional to match model
    category_id: Optional[int] = None  # Changed to optional to match model
    deliverect_item_id: Optional[str] = None  # Added missing field
    location_id: Optional[str] = None  # Added missing field
    is_available: bool = True
    is_combo: bool = False  # Added missing field
    is_variant: bool = False  # Added missing field
    image_url: Optional[str] = None
    order_index: int = 0  # Added missing field
    properties: Optional[Dict[str, Any]] = None  # Added missing field


class MenuItemCreate(MenuItemBase):
    pass


class MenuItemUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    plu: Optional[str] = None
    category_id: Optional[int] = None
    deliverect_item_id: Optional[str] = None  # Added missing field
    location_id: Optional[str] = None  # Added missing field
    is_available: Optional[bool] = None
    is_combo: Optional[bool] = None  # Added missing field
    is_variant: Optional[bool] = None  # Added missing field
    image_url: Optional[str] = None
    order_index: Optional[int] = None  # Added missing field
    properties: Optional[Dict[str, Any]] = None  # Added missing field


class MenuModifierBase(BaseModel):
    name: str
    description: Optional[str] = None
    price_change: float = 0.0  # Price change (can be decimal)
    plu: Optional[str] = None  # Changed to optional to match model
    deliverect_modifier_id: Optional[str] = None  # Added missing field
    location_id: Optional[str] = None  # Added missing field
    is_available: bool = True
    properties: Optional[Dict[str, Any]] = None  # Added missing field


class MenuModifierCreate(MenuModifierBase):
    pass


class MenuModifierUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price_change: Optional[float] = None
    plu: Optional[str] = None
    deliverect_modifier_id: Optional[str] = None  # Added missing field
    location_id: Optional[str] = None  # Added missing field
    is_available: Optional[bool] = None
    properties: Optional[Dict[str, Any]] = None  # Added missing field


class MenuModifierGroupBase(BaseModel):
    name: str
    description: Optional[str] = None
    min_selection: int = 0
    max_selection: int = 0  # Changed to int to match model
    multiMax: int = 0  # Added missing field to match model
    plu: Optional[str] = None  # Added missing field
    deliverect_group_id: Optional[str] = None  # Added missing field
    location_id: Optional[str] = None  # Added missing field
    is_variant_group: bool = False  # Added missing field
    properties: Optional[Dict[str, Any]] = None  # Added missing field


class MenuModifierGroupCreate(MenuModifierGroupBase):
    pass


class MenuModifierGroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    min_selection: Optional[int] = None
    max_selection: Optional[int] = None
    multiMax: Optional[int] = None  # Added missing field
    plu: Optional[str] = None  # Added missing field
    deliverect_group_id: Optional[str] = None  # Added missing field
    location_id: Optional[str] = None  # Added missing field
    is_variant_group: Optional[bool] = None  # Added missing field
    properties: Optional[Dict[str, Any]] = None  # Added missing field


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
    
    class Config:
        # Allow extra fields that might be added by Deliverect
        extra = "allow"
    
    
class MenuSyncResponse(BaseModel):
    """Response after processing menu webhook"""
    success: bool
    message: str
    items_processed: int
    categories_processed: int
    modifiers_processed: int
    errors: Optional[List[str]] = []
    warnings: Optional[List[str]] = []
    
    
# Enhanced validation schema for robust webhook processing
class FlexibleDeliverectProduct(BaseModel):
    """More flexible product schema that handles various Deliverect formats"""
    _id: str
    name: str
    description: Optional[str] = ""
    account: str
    location: str
    plu: str
    price: Optional[float] = 0.0  # Handle both int and float
    productType: int
    
    # Optional fields with flexible typing
    deliveryTax: Optional[float] = 0.0
    eatInTax: Optional[float] = 0.0
    takeawayTax: Optional[float] = 0.0
    imageUrl: Optional[str] = ""
    max: Optional[int] = 0
    min: Optional[int] = 0
    multiply: Optional[int] = 1
    snoozed: Optional[bool] = False
    available: Optional[bool] = True
    parentId: Optional[str] = None
    
    # Handle various field formats
    modifierGroups: Optional[List] = []
    subProducts: Optional[List] = []
    productTags: Optional[List] = []
    
    class Config:
        # Allow extra fields and flexible validation
        extra = "allow"
        # Convert strings to appropriate types
        str_to_lower = False
        validate_assignment = True
        
    @validator('price', pre=True)
    def convert_price(cls, v):
        """Convert price to float, handling both int and float inputs"""
        if v is None:
            return 0.0
        if isinstance(v, str):
            try:
                return float(v)
            except ValueError:
                return 0.0
        return float(v)
    
    @validator('deliveryTax', 'eatInTax', 'takeawayTax', pre=True)
    def convert_tax(cls, v):
        """Convert tax values to float, handling various formats"""
        if v is None:
            return 0.0
        if isinstance(v, str):
            try:
                return float(v)
            except ValueError:
                return 0.0
        return float(v)


class FlexibleDeliverectCategory(BaseModel):
    """More flexible category schema that handles various Deliverect formats"""
    _id: str
    name: str
    account: str
    menu: str
    level: Optional[int] = 1
    
    # Optional fields with flexible typing
    description: Optional[str] = ""
    imageUrl: Optional[str] = ""
    products: Optional[List] = []
    subCategories: Optional[List] = []
    available: Optional[bool] = True
    position: Optional[int] = 0
    
    class Config:
        # Allow extra fields and flexible validation
        extra = "allow"
        validate_assignment = True


class FlexibleMenuWebhookPayload(BaseModel):
    """More flexible webhook payload schema"""
    payload: List[Dict[str, Any]]  # Accept raw dictionaries for preprocessing
    
    class Config:
        extra = "allow"