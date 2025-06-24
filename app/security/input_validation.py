"""
Input validation for RedBarSushiAI.

This module provides comprehensive input validation for all user inputs,
API parameters, and tool function arguments to prevent injection attacks
and ensure data integrity.
"""

import re
import json
from typing import Any, Dict, List, Optional, Union, Callable
from dataclasses import dataclass
from enum import Enum
import logging

from pydantic import BaseModel, Field, validator, ValidationError
from pydantic import constr, conint, confloat

logger = logging.getLogger(__name__)


class ValidationLevel(Enum):
    """Validation strictness levels."""
    STRICT = "strict"      # Reject any suspicious input
    MODERATE = "moderate"  # Allow some flexibility
    LENIENT = "lenient"    # Minimal validation


@dataclass
class ValidationResult:
    """Result of input validation."""
    is_valid: bool
    sanitized_value: Any
    error_message: Optional[str] = None
    risk_level: Optional[str] = None


class BaseValidator:
    """Base class for input validators."""
    
    def __init__(self, level: ValidationLevel = ValidationLevel.MODERATE):
        """Initialize validator with strictness level."""
        self.level = level
    
    def validate(self, value: Any) -> ValidationResult:
        """Validate input value."""
        raise NotImplementedError


class TextValidator(BaseValidator):
    """Validator for text inputs."""
    
    # Patterns that might indicate injection attempts
    SUSPICIOUS_PATTERNS = [
        r'<script[^>]*>.*?</script>',  # Script tags
        r'javascript:',                 # JavaScript protocol
        r'on\w+\s*=',                  # Event handlers
        r'<iframe',                     # Iframes
        r'<object',                     # Objects
        r'<embed',                      # Embeds
        r'\$\{.*\}',                   # Template injection
        r'\{\{.*\}\}',                 # Template injection
        r'exec\s*\(',                  # Code execution
        r'eval\s*\(',                  # Code evaluation
        r'__.*__',                     # Python magic methods
        r'import\s+',                  # Import statements
        r'require\s*\(',               # Require statements
        r'SELECT.*FROM',               # SQL queries
        r'INSERT.*INTO',               # SQL insertion
        r'UPDATE.*SET',                # SQL update
        r'DELETE.*FROM',               # SQL deletion
        r'DROP\s+TABLE',               # SQL drop
        r'--\s*$',                     # SQL comment
        r';\s*$',                      # Statement terminator
        r'\\x[0-9a-fA-F]+',           # Hex encoding
        r'\\u[0-9a-fA-F]{4}',         # Unicode encoding
    ]
    
    # Maximum lengths for different text types
    MAX_LENGTHS = {
        'name': 100,
        'phone': 20,
        'address': 500,
        'message': 1000,
        'transcript': 2000,
        'default': 5000
    }
    
    def __init__(
        self,
        max_length: Optional[int] = None,
        text_type: str = 'default',
        allow_unicode: bool = True,
        level: ValidationLevel = ValidationLevel.MODERATE
    ):
        """Initialize text validator."""
        super().__init__(level)
        self.max_length = max_length or self.MAX_LENGTHS.get(text_type, self.MAX_LENGTHS['default'])
        self.text_type = text_type
        self.allow_unicode = allow_unicode
    
    def validate(self, value: Any) -> ValidationResult:
        """Validate text input."""
        if value is None:
            return ValidationResult(is_valid=True, sanitized_value='')
        
        # Convert to string
        text = str(value)
        
        # Check length
        if len(text) > self.max_length:
            return ValidationResult(
                is_valid=False,
                sanitized_value=text[:self.max_length],
                error_message=f"Text exceeds maximum length of {self.max_length}"
            )
        
        # Check for suspicious patterns
        risk_level = None
        if self.level != ValidationLevel.LENIENT:
            for pattern in self.SUSPICIOUS_PATTERNS:
                if re.search(pattern, text, re.IGNORECASE):
                    if self.level == ValidationLevel.STRICT:
                        return ValidationResult(
                            is_valid=False,
                            sanitized_value='',
                            error_message=f"Suspicious pattern detected: {pattern}",
                            risk_level='high'
                        )
                    else:  # MODERATE
                        risk_level = 'medium'
                        logger.warning(f"Suspicious pattern detected in input: {pattern}")
        
        # Sanitize based on text type
        sanitized = self._sanitize_text(text)
        
        return ValidationResult(
            is_valid=True,
            sanitized_value=sanitized,
            risk_level=risk_level
        )
    
    def _sanitize_text(self, text: str) -> str:
        """Sanitize text based on type."""
        if self.text_type == 'name':
            # Allow letters, spaces, hyphens, apostrophes
            sanitized = re.sub(r'[^a-zA-Z\s\-\']', '', text)
        elif self.text_type == 'phone':
            # Allow digits, spaces, hyphens, parentheses, plus
            sanitized = re.sub(r'[^\d\s\-\(\)\+]', '', text)
        elif self.text_type == 'address':
            # Allow alphanumeric, spaces, common punctuation
            sanitized = re.sub(r'[^a-zA-Z0-9\s\-\.,#]', '', text)
        else:
            # General sanitization - remove control characters
            sanitized = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', text)
            
            # Remove script tags and dangerous HTML
            sanitized = re.sub(r'<script[^>]*>.*?</script>', '', sanitized, flags=re.IGNORECASE | re.DOTALL)
            sanitized = re.sub(r'<[^>]+>', '', sanitized)  # Remove all HTML tags
        
        return sanitized.strip()


class NumberValidator(BaseValidator):
    """Validator for numeric inputs."""
    
    def __init__(
        self,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        allow_negative: bool = False,
        allow_decimal: bool = True,
        level: ValidationLevel = ValidationLevel.MODERATE
    ):
        """Initialize number validator."""
        super().__init__(level)
        self.min_value = min_value
        self.max_value = max_value
        self.allow_negative = allow_negative
        self.allow_decimal = allow_decimal
    
    def validate(self, value: Any) -> ValidationResult:
        """Validate numeric input."""
        try:
            # Convert to float
            if self.allow_decimal:
                num = float(value)
            else:
                num = int(value)
        except (ValueError, TypeError):
            return ValidationResult(
                is_valid=False,
                sanitized_value=0,
                error_message=f"Invalid number format: {value}"
            )
        
        # Check negative
        if not self.allow_negative and num < 0:
            return ValidationResult(
                is_valid=False,
                sanitized_value=abs(num),
                error_message="Negative numbers not allowed"
            )
        
        # Check range
        if self.min_value is not None and num < self.min_value:
            return ValidationResult(
                is_valid=False,
                sanitized_value=self.min_value,
                error_message=f"Value {num} is below minimum {self.min_value}"
            )
        
        if self.max_value is not None and num > self.max_value:
            return ValidationResult(
                is_valid=False,
                sanitized_value=self.max_value,
                error_message=f"Value {num} exceeds maximum {self.max_value}"
            )
        
        return ValidationResult(is_valid=True, sanitized_value=num)


class ListValidator(BaseValidator):
    """Validator for list inputs."""
    
    def __init__(
        self,
        item_validator: BaseValidator,
        min_items: int = 0,
        max_items: int = 100,
        level: ValidationLevel = ValidationLevel.MODERATE
    ):
        """Initialize list validator."""
        super().__init__(level)
        self.item_validator = item_validator
        self.min_items = min_items
        self.max_items = max_items
    
    def validate(self, value: Any) -> ValidationResult:
        """Validate list input."""
        if not isinstance(value, list):
            return ValidationResult(
                is_valid=False,
                sanitized_value=[],
                error_message="Input must be a list"
            )
        
        # Check size
        if len(value) < self.min_items:
            return ValidationResult(
                is_valid=False,
                sanitized_value=value,
                error_message=f"List must have at least {self.min_items} items"
            )
        
        if len(value) > self.max_items:
            return ValidationResult(
                is_valid=False,
                sanitized_value=value[:self.max_items],
                error_message=f"List exceeds maximum of {self.max_items} items"
            )
        
        # Validate each item
        sanitized_items = []
        all_valid = True
        
        for item in value:
            result = self.item_validator.validate(item)
            if not result.is_valid:
                all_valid = False
                if self.level == ValidationLevel.STRICT:
                    return ValidationResult(
                        is_valid=False,
                        sanitized_value=[],
                        error_message=f"Invalid item in list: {result.error_message}"
                    )
            sanitized_items.append(result.sanitized_value)
        
        return ValidationResult(
            is_valid=all_valid,
            sanitized_value=sanitized_items
        )


# Pydantic models for structured validation

class CustomerNameInput(BaseModel):
    """Validate customer name input."""
    name: constr(min_length=1, max_length=100, regex=r'^[a-zA-Z\s\-\']+$')
    
    @validator('name')
    def validate_name(cls, v):
        # Additional validation
        if len(v.split()) > 5:  # Reasonable limit on name parts
            raise ValueError("Name contains too many parts")
        return v.strip()


class PhoneNumberInput(BaseModel):
    """Validate phone number input."""
    phone: constr(min_length=10, max_length=20, regex=r'^[\d\s\-\(\)\+]+$')
    
    @validator('phone')
    def validate_phone(cls, v):
        # Remove formatting
        digits = re.sub(r'\D', '', v)
        if len(digits) < 10 or len(digits) > 15:
            raise ValueError("Invalid phone number length")
        return v


class AddressInput(BaseModel):
    """Validate address input."""
    street: constr(min_length=5, max_length=200)
    city: constr(min_length=2, max_length=100)
    state: Optional[constr(min_length=2, max_length=50)] = None
    zip_code: Optional[constr(regex=r'^\d{5}(-\d{4})?$')] = None
    
    @validator('street', 'city', 'state')
    def sanitize_address_fields(cls, v):
        if v:
            # Remove potentially dangerous characters
            return re.sub(r'[<>\"\';&]', '', v)
        return v


class MenuItemInput(BaseModel):
    """Validate menu item selection."""
    item_name: constr(min_length=1, max_length=200)
    quantity: conint(ge=1, le=100)  # Between 1 and 100
    modifications: Optional[List[str]] = Field(default_factory=list)
    
    @validator('item_name')
    def validate_item_name(cls, v):
        # Basic sanitization
        return re.sub(r'[<>\"\';&]', '', v).strip()
    
    @validator('modifications')
    def validate_modifications(cls, v):
        if v and len(v) > 10:
            raise ValueError("Too many modifications")
        return [re.sub(r'[<>\"\';&]', '', mod).strip() for mod in v if mod]


class TranscriptInput(BaseModel):
    """Validate voice transcript input."""
    transcript: constr(max_length=2000)
    confidence: Optional[confloat(ge=0.0, le=1.0)] = None
    
    @validator('transcript')
    def sanitize_transcript(cls, v):
        # Remove control characters and excessive whitespace
        sanitized = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', v)
        sanitized = re.sub(r'\s+', ' ', sanitized)
        return sanitized.strip()


# Tool parameter validators

class SearchMenuParameters(BaseModel):
    """Validate search_menu tool parameters."""
    query: constr(min_length=1, max_length=200)
    category: Optional[constr(max_length=100)] = None
    dietary_restrictions: Optional[List[constr(max_length=50)]] = Field(default_factory=list)
    
    @validator('query', 'category')
    def sanitize_search_params(cls, v):
        if v:
            # Remove SQL-like patterns
            if re.search(r'(SELECT|FROM|WHERE|JOIN|UNION)', v, re.IGNORECASE):
                raise ValueError("Invalid search query")
            return v.strip()
        return v


class AddToCartParameters(BaseModel):
    """Validate add_to_cart tool parameters."""
    item_name: constr(min_length=1, max_length=200)
    quantity: conint(ge=1, le=50)
    modifications: Optional[List[constr(max_length=100)]] = Field(default_factory=list)
    special_instructions: Optional[constr(max_length=500)] = None


# Main validation interface

class InputValidator:
    """Central input validation service."""
    
    def __init__(self, level: ValidationLevel = ValidationLevel.MODERATE):
        """Initialize input validator."""
        self.level = level
        self.text_validator = TextValidator(level=level)
        self.number_validator = NumberValidator(level=level)
    
    def validate_customer_name(self, name: str) -> ValidationResult:
        """Validate customer name."""
        try:
            validated = CustomerNameInput(name=name)
            return ValidationResult(
                is_valid=True,
                sanitized_value=validated.name
            )
        except ValidationError as e:
            return ValidationResult(
                is_valid=False,
                sanitized_value='',
                error_message=str(e)
            )
    
    def validate_phone_number(self, phone: str) -> ValidationResult:
        """Validate phone number."""
        try:
            validated = PhoneNumberInput(phone=phone)
            return ValidationResult(
                is_valid=True,
                sanitized_value=validated.phone
            )
        except ValidationError as e:
            return ValidationResult(
                is_valid=False,
                sanitized_value='',
                error_message=str(e)
            )
    
    def validate_transcript(self, transcript: str, confidence: float = None) -> ValidationResult:
        """Validate voice transcript."""
        try:
            validated = TranscriptInput(
                transcript=transcript,
                confidence=confidence
            )
            return ValidationResult(
                is_valid=True,
                sanitized_value=validated.transcript
            )
        except ValidationError as e:
            return ValidationResult(
                is_valid=False,
                sanitized_value='',
                error_message=str(e)
            )
    
    def validate_menu_search(self, **params) -> ValidationResult:
        """Validate menu search parameters."""
        try:
            validated = SearchMenuParameters(**params)
            return ValidationResult(
                is_valid=True,
                sanitized_value=validated.dict()
            )
        except ValidationError as e:
            return ValidationResult(
                is_valid=False,
                sanitized_value={},
                error_message=str(e)
            )
    
    def validate_cart_addition(self, **params) -> ValidationResult:
        """Validate cart addition parameters."""
        try:
            validated = AddToCartParameters(**params)
            return ValidationResult(
                is_valid=True,
                sanitized_value=validated.dict()
            )
        except ValidationError as e:
            return ValidationResult(
                is_valid=False,
                sanitized_value={},
                error_message=str(e)
            )
    
    def validate_json(self, json_str: str, max_size: int = 1_000_000) -> ValidationResult:
        """Validate JSON input."""
        if len(json_str) > max_size:
            return ValidationResult(
                is_valid=False,
                sanitized_value={},
                error_message=f"JSON exceeds maximum size of {max_size} bytes"
            )
        
        try:
            data = json.loads(json_str)
            
            # Check for dangerous keys
            dangerous_keys = ['__proto__', 'constructor', 'prototype']
            
            def check_dangerous_keys(obj):
                if isinstance(obj, dict):
                    for key in obj:
                        if key in dangerous_keys:
                            return True
                        if check_dangerous_keys(obj[key]):
                            return True
                elif isinstance(obj, list):
                    for item in obj:
                        if check_dangerous_keys(item):
                            return True
                return False
            
            if check_dangerous_keys(data):
                return ValidationResult(
                    is_valid=False,
                    sanitized_value={},
                    error_message="JSON contains dangerous keys",
                    risk_level='high'
                )
            
            return ValidationResult(
                is_valid=True,
                sanitized_value=data
            )
            
        except json.JSONDecodeError as e:
            return ValidationResult(
                is_valid=False,
                sanitized_value={},
                error_message=f"Invalid JSON: {e}"
            )
    
    def sanitize_for_llm(self, text: str) -> str:
        """Sanitize text before sending to LLM."""
        # Remove potential prompt injection patterns
        patterns_to_remove = [
            r'ignore\s+(previous|all)\s+instructions',
            r'disregard\s+.*\s+instructions',
            r'forget\s+everything',
            r'new\s+instructions:',
            r'system\s*:',
            r'assistant\s*:',
            r'<\|.*\|>',  # Special tokens
            r'\[\[.*\]\]',  # Special markers
        ]
        
        sanitized = text
        for pattern in patterns_to_remove:
            sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE)
        
        # Limit length
        if len(sanitized) > 1000:
            sanitized = sanitized[:1000] + "..."
        
        return sanitized.strip()


# Singleton instance
input_validator = InputValidator()