"""
Output sanitization for RedBarSushiAI.

This module provides sanitization for LLM outputs to prevent injection
of malicious content, inappropriate language, and sensitive information
before sending to users.
"""

import re
import json
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class SanitizationType(Enum):
    """Types of content to sanitize."""
    PERSONAL_INFO = "personal_info"
    PROFANITY = "profanity"
    INJECTION = "injection"
    URLS = "urls"
    SCRIPTS = "scripts"
    SENSITIVE_BUSINESS = "sensitive_business"


@dataclass
class SanitizationResult:
    """Result of output sanitization."""
    sanitized_text: str
    original_text: str
    modifications_made: bool
    detected_issues: List[str]
    risk_level: str  # low, medium, high


class OutputSanitizer:
    """Sanitizes LLM outputs before sending to users."""
    
    def __init__(self, strict_mode: bool = False):
        """
        Initialize output sanitizer.
        
        Args:
            strict_mode: If True, more aggressive sanitization
        """
        self.strict_mode = strict_mode
        self._load_patterns()
    
    def _load_patterns(self):
        """Load sanitization patterns."""
        # Personal information patterns
        self.pii_patterns = {
            'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
            'credit_card': r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b',
            'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'phone': r'\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b',
            'ip_address': r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
            'api_key': r'\b[A-Za-z0-9]{32,}\b',  # Generic long string
        }
        
        # Inappropriate content patterns (basic list - extend as needed)
        self.profanity_patterns = [
            # Add actual patterns here - keeping family-friendly in example
            r'\b(darn|heck|crud)\b',  # Mild examples
        ]
        
        # Injection patterns
        self.injection_patterns = {
            'script_tags': r'<script[^>]*>.*?</script>',
            'style_tags': r'<style[^>]*>.*?</style>',
            'event_handlers': r'on\w+\s*=\s*["\'].*?["\']',
            'javascript_protocol': r'javascript:',
            'data_protocol': r'data:.*base64',
            'iframe': r'<iframe[^>]*>',
            'object_embed': r'<(object|embed)[^>]*>',
            'markdown_script': r'```[^`]*<script',
            'system_prompts': r'(system|assistant|human):\s*["\'].*["\']',
            'prompt_injection': r'ignore\s+previous\s+instructions',
        }
        
        # URL patterns
        self.url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+|www\.[^\s<>"{}|\\^`\[\]]+'
        
        # Sensitive business information
        self.business_patterns = {
            'internal_api': r'/api/internal/',
            'database_names': r'(postgres|mysql|mongodb)://[^\s]+',
            'file_paths': r'(/usr/|/etc/|/var/|C:\\|\\\\)[^\s]+',
            'environment_vars': r'\$\{?[A-Z_]+\}?',
            'stack_traces': r'Traceback \(most recent call last\)',
            'error_details': r'at line \d+ in file',
        }
    
    def sanitize(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> SanitizationResult:
        """
        Sanitize LLM output text.
        
        Args:
            text: The text to sanitize
            context: Optional context for better sanitization
            
        Returns:
            SanitizationResult with sanitized text and details
        """
        original_text = text
        sanitized_text = text
        detected_issues = []
        modifications_made = False
        
        # Check for personal information
        pii_result = self._sanitize_pii(sanitized_text)
        if pii_result[1]:
            sanitized_text = pii_result[0]
            detected_issues.extend(pii_result[2])
            modifications_made = True
        
        # Check for inappropriate content
        if self.strict_mode:
            profanity_result = self._sanitize_profanity(sanitized_text)
            if profanity_result[1]:
                sanitized_text = profanity_result[0]
                detected_issues.append("inappropriate_content")
                modifications_made = True
        
        # Check for injection attempts
        injection_result = self._sanitize_injections(sanitized_text)
        if injection_result[1]:
            sanitized_text = injection_result[0]
            detected_issues.extend(injection_result[2])
            modifications_made = True
        
        # Handle URLs
        url_result = self._sanitize_urls(sanitized_text, context)
        if url_result[1]:
            sanitized_text = url_result[0]
            detected_issues.append("unauthorized_urls")
            modifications_made = True
        
        # Check for sensitive business information
        business_result = self._sanitize_business_info(sanitized_text)
        if business_result[1]:
            sanitized_text = business_result[0]
            detected_issues.extend(business_result[2])
            modifications_made = True
        
        # Additional context-specific sanitization
        if context:
            context_result = self._context_specific_sanitization(sanitized_text, context)
            if context_result[1]:
                sanitized_text = context_result[0]
                detected_issues.extend(context_result[2])
                modifications_made = True
        
        # Determine risk level
        risk_level = self._assess_risk_level(detected_issues)
        
        # Log if modifications were made
        if modifications_made:
            logger.warning(
                f"Output sanitization applied. Issues: {detected_issues}, "
                f"Risk level: {risk_level}"
            )
        
        return SanitizationResult(
            sanitized_text=sanitized_text,
            original_text=original_text,
            modifications_made=modifications_made,
            detected_issues=detected_issues,
            risk_level=risk_level
        )
    
    def _sanitize_pii(self, text: str) -> Tuple[str, bool, List[str]]:
        """Sanitize personal information."""
        modified = False
        issues = []
        
        for pii_type, pattern in self.pii_patterns.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                modified = True
                issues.append(f"pii_{pii_type}")
                
                # Replace with generic placeholder
                if pii_type == 'email':
                    text = re.sub(pattern, '[EMAIL_REMOVED]', text, flags=re.IGNORECASE)
                elif pii_type == 'phone':
                    text = re.sub(pattern, '[PHONE_REMOVED]', text, flags=re.IGNORECASE)
                elif pii_type == 'ssn':
                    text = re.sub(pattern, '[SSN_REMOVED]', text, flags=re.IGNORECASE)
                elif pii_type == 'credit_card':
                    text = re.sub(pattern, '[CC_REMOVED]', text, flags=re.IGNORECASE)
                else:
                    text = re.sub(pattern, '[REDACTED]', text, flags=re.IGNORECASE)
        
        return text, modified, issues
    
    def _sanitize_profanity(self, text: str) -> Tuple[str, bool]:
        """Sanitize inappropriate language."""
        modified = False
        
        for pattern in self.profanity_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                text = re.sub(pattern, '[*]', text, flags=re.IGNORECASE)
                modified = True
        
        return text, modified
    
    def _sanitize_injections(self, text: str) -> Tuple[str, bool, List[str]]:
        """Sanitize potential injection attempts."""
        modified = False
        issues = []
        
        for injection_type, pattern in self.injection_patterns.items():
            if re.search(pattern, text, re.IGNORECASE | re.DOTALL):
                modified = True
                issues.append(f"injection_{injection_type}")
                
                # Remove or neutralize the pattern
                if injection_type in ['script_tags', 'style_tags', 'iframe', 'object_embed']:
                    text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.DOTALL)
                elif injection_type == 'event_handlers':
                    text = re.sub(pattern, 'data-disabled="true"', text, flags=re.IGNORECASE)
                elif injection_type in ['javascript_protocol', 'data_protocol']:
                    text = re.sub(pattern, '#', text, flags=re.IGNORECASE)
                elif injection_type == 'prompt_injection':
                    # Log and remove entirely
                    logger.error("Potential prompt injection detected in output")
                    text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        return text, modified, issues
    
    def _sanitize_urls(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, bool]:
        """Sanitize URLs based on allowlist."""
        # Allowed domains
        allowed_domains = [
            'redbarsushi.com',
            'example.com',  # Add actual allowed domains
        ]
        
        if context and 'allowed_urls' in context:
            allowed_domains.extend(context['allowed_urls'])
        
        modified = False
        urls = re.findall(self.url_pattern, text)
        
        for url in urls:
            # Check if URL is from allowed domain
            allowed = any(domain in url for domain in allowed_domains)
            
            if not allowed:
                text = text.replace(url, '[URL_REMOVED]')
                modified = True
        
        return text, modified
    
    def _sanitize_business_info(self, text: str) -> Tuple[str, bool, List[str]]:
        """Sanitize sensitive business information."""
        modified = False
        issues = []
        
        for info_type, pattern in self.business_patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                modified = True
                issues.append(f"business_{info_type}")
                
                if info_type == 'internal_api':
                    text = re.sub(pattern, '/api/[REDACTED]/', text, flags=re.IGNORECASE)
                elif info_type == 'database_names':
                    text = re.sub(pattern, '[DATABASE_URL_REDACTED]', text, flags=re.IGNORECASE)
                elif info_type == 'file_paths':
                    text = re.sub(pattern, '[PATH_REDACTED]', text, flags=re.IGNORECASE)
                elif info_type == 'environment_vars':
                    text = re.sub(pattern, '[ENV_VAR]', text, flags=re.IGNORECASE)
                else:
                    text = re.sub(pattern, '[TECHNICAL_DETAILS_REMOVED]', text, flags=re.IGNORECASE)
        
        return text, modified, issues
    
    def _context_specific_sanitization(
        self,
        text: str,
        context: Dict[str, Any]
    ) -> Tuple[str, bool, List[str]]:
        """Apply context-specific sanitization rules."""
        modified = False
        issues = []
        
        # Don't reveal system internals
        if 'conversation_state' in context:
            state_patterns = [
                r'FSM state:?\s*\w+',
                r'current_state:?\s*\w+',
                r'transition to \w+',
            ]
            
            for pattern in state_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    text = re.sub(pattern, '', text, flags=re.IGNORECASE)
                    modified = True
                    issues.append("internal_state_leak")
        
        # Don't reveal other customer information
        if 'customer_name' in context:
            # Remove any names that aren't the current customer's
            other_names_pattern = r'\b[A-Z][a-z]+\s+[A-Z][a-z]+\b'
            current_name = context['customer_name']
            
            potential_names = re.findall(other_names_pattern, text)
            for name in potential_names:
                if name != current_name and name not in ['Red Bar', 'Bar Sushi']:
                    text = text.replace(name, '[NAME_REDACTED]')
                    modified = True
                    issues.append("other_customer_info")
        
        # Sanitize price discussions in certain contexts
        if context.get('hide_pricing', False):
            price_pattern = r'\$\d+\.?\d*'
            text = re.sub(price_pattern, '[PRICE]', text)
            modified = True
            issues.append("pricing_hidden")
        
        return text, modified, issues
    
    def _assess_risk_level(self, issues: List[str]) -> str:
        """Assess overall risk level based on detected issues."""
        high_risk_issues = [
            'injection_script_tags',
            'injection_prompt_injection',
            'pii_ssn',
            'pii_credit_card',
            'business_internal_api',
            'business_database_names'
        ]
        
        medium_risk_issues = [
            'injection_event_handlers',
            'pii_email',
            'pii_phone',
            'business_file_paths',
            'other_customer_info'
        ]
        
        if any(issue in high_risk_issues for issue in issues):
            return 'high'
        elif any(issue in medium_risk_issues for issue in issues):
            return 'medium'
        elif issues:
            return 'low'
        else:
            return 'none'
    
    def sanitize_json_response(
        self,
        data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Sanitize JSON response data.
        
        Args:
            data: The JSON data to sanitize
            context: Optional context
            
        Returns:
            Sanitized JSON data
        """
        def sanitize_value(value: Any) -> Any:
            if isinstance(value, str):
                result = self.sanitize(value, context)
                return result.sanitized_text
            elif isinstance(value, dict):
                return {k: sanitize_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [sanitize_value(item) for item in value]
            else:
                return value
        
        return sanitize_value(data)


# Specialized sanitizers for different contexts

class MenuResponseSanitizer(OutputSanitizer):
    """Specialized sanitizer for menu-related responses."""
    
    def __init__(self):
        super().__init__()
        # Add menu-specific patterns
        self.menu_patterns = {
            'internal_plu': r'PLU:?\s*\w+',
            'cost_price': r'cost:?\s*\$?\d+\.?\d*',
            'supplier_info': r'supplier:?\s*\w+',
        }
    
    def sanitize(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> SanitizationResult:
        """Sanitize menu response with additional checks."""
        # First apply general sanitization
        result = super().sanitize(text, context)
        
        # Then apply menu-specific sanitization
        sanitized_text = result.sanitized_text
        
        for pattern_name, pattern in self.menu_patterns.items():
            if re.search(pattern, sanitized_text, re.IGNORECASE):
                sanitized_text = re.sub(pattern, '', sanitized_text, flags=re.IGNORECASE)
                result.detected_issues.append(f"menu_{pattern_name}")
                result.modifications_made = True
        
        result.sanitized_text = sanitized_text
        return result


class OrderConfirmationSanitizer(OutputSanitizer):
    """Specialized sanitizer for order confirmations."""
    
    def sanitize(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> SanitizationResult:
        """Sanitize order confirmation with specific rules."""
        # Ensure we don't leak other orders
        order_id_pattern = r'[A-Z]{3}-\d{5,}'
        current_order_id = context.get('order_id') if context else None
        
        # Find all order IDs
        order_ids = re.findall(order_id_pattern, text)
        
        # Replace any that aren't the current order
        for order_id in order_ids:
            if order_id != current_order_id:
                text = text.replace(order_id, '[ORDER_ID_REDACTED]')
        
        # Apply general sanitization
        return super().sanitize(text, context)


# Global sanitizer instances
general_sanitizer = OutputSanitizer()
strict_sanitizer = OutputSanitizer(strict_mode=True)
menu_sanitizer = MenuResponseSanitizer()
order_sanitizer = OrderConfirmationSanitizer()


# Utility functions

def sanitize_llm_output(
    text: str,
    output_type: str = 'general',
    context: Optional[Dict[str, Any]] = None,
    strict: bool = False
) -> str:
    """
    Convenience function to sanitize LLM output.
    
    Args:
        text: The text to sanitize
        output_type: Type of output (general, menu, order)
        context: Optional context
        strict: Whether to use strict mode
        
    Returns:
        Sanitized text
    """
    if output_type == 'menu':
        sanitizer = menu_sanitizer
    elif output_type == 'order':
        sanitizer = order_sanitizer
    elif strict:
        sanitizer = strict_sanitizer
    else:
        sanitizer = general_sanitizer
    
    result = sanitizer.sanitize(text, context)
    
    # Log high-risk sanitizations
    if result.risk_level == 'high':
        logger.error(
            f"High-risk content sanitized: {result.detected_issues}"
        )
    
    return result.sanitized_text


def create_safe_error_message(
    error: Exception,
    user_friendly: bool = True
) -> str:
    """
    Create a safe error message from an exception.
    
    Args:
        error: The exception
        user_friendly: Whether to make it user-friendly
        
    Returns:
        Safe error message
    """
    # Never expose internal error details to users
    error_str = str(error)
    
    # Remove sensitive patterns
    sensitive_patterns = [
        r'at 0x[0-9a-fA-F]+',  # Memory addresses
        r'File "[^"]+", line \d+',  # File paths
        r'/\w+/\w+/\w+',  # Unix paths
        r'[A-Z]:\\[^\\]+\\',  # Windows paths
        r'postgres://[^@]+@',  # Database URLs
    ]
    
    for pattern in sensitive_patterns:
        error_str = re.sub(pattern, '[REDACTED]', error_str)
    
    if user_friendly:
        # Map technical errors to user-friendly messages
        error_mappings = {
            'connection': "We're having connection issues. Please try again.",
            'timeout': "The request took too long. Please try again.",
            'database': "We're experiencing technical difficulties.",
            'api': "Service temporarily unavailable.",
        }
        
        for key, message in error_mappings.items():
            if key in error_str.lower():
                return message
        
        # Generic message
        return "Something went wrong. Please try again or contact support."
    
    return error_str