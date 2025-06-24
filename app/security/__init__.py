"""
Security module for RedBarSushiAI.

This module provides comprehensive security features including input validation,
output sanitization, rate limiting, and webhook authentication.
"""

from .input_validation import (
    InputValidator,
    ValidationResult,
    ValidationLevel,
    TextValidator,
    NumberValidator,
    ListValidator,
    input_validator,
    # Pydantic models
    CustomerNameInput,
    PhoneNumberInput,
    AddressInput,
    MenuItemInput,
    TranscriptInput,
    SearchMenuParameters,
    AddToCartParameters
)

from .output_sanitization import (
    OutputSanitizer,
    SanitizationResult,
    SanitizationType,
    MenuResponseSanitizer,
    OrderConfirmationSanitizer,
    general_sanitizer,
    strict_sanitizer,
    menu_sanitizer,
    order_sanitizer,
    sanitize_llm_output,
    create_safe_error_message
)

from .rate_limiting import (
    RateLimiter,
    RateLimitConfig,
    RateLimitType,
    RateLimitManager,
    rate_limit_manager,
    check_api_rate_limit,
    check_websocket_rate_limit,
    check_llm_rate_limit,
    check_order_rate_limit,
    check_custom_rate_limit,
    rate_limit,
    RateLimitMiddleware
)

from .webhook_security import (
    WebhookSigner,
    TwilioWebhookVerifier,
    DeliverectWebhookVerifier,
    WebhookAuthMiddleware,
    WebhookRateLimiter,
    webhook_auth,
    webhook_rate_limiter,
    require_twilio_webhook,
    require_deliverect_webhook,
    require_webhook_auth,
    check_webhook_rate_limit,
    generate_webhook_secret,
    create_webhook_headers
)

__all__ = [
    # Input validation
    'InputValidator',
    'ValidationResult',
    'ValidationLevel',
    'TextValidator',
    'NumberValidator',
    'ListValidator',
    'input_validator',
    'CustomerNameInput',
    'PhoneNumberInput',
    'AddressInput',
    'MenuItemInput',
    'TranscriptInput',
    'SearchMenuParameters',
    'AddToCartParameters',
    
    # Output sanitization
    'OutputSanitizer',
    'SanitizationResult',
    'SanitizationType',
    'MenuResponseSanitizer',
    'OrderConfirmationSanitizer',
    'general_sanitizer',
    'strict_sanitizer',
    'menu_sanitizer',
    'order_sanitizer',
    'sanitize_llm_output',
    'create_safe_error_message',
    
    # Rate limiting
    'RateLimiter',
    'RateLimitConfig',
    'RateLimitType',
    'RateLimitManager',
    'rate_limit_manager',
    'check_api_rate_limit',
    'check_websocket_rate_limit',
    'check_llm_rate_limit',
    'check_order_rate_limit',
    'check_custom_rate_limit',
    'rate_limit',
    'RateLimitMiddleware',
    
    # Webhook security
    'WebhookSigner',
    'TwilioWebhookVerifier',
    'DeliverectWebhookVerifier',
    'WebhookAuthMiddleware',
    'WebhookRateLimiter',
    'webhook_auth',
    'webhook_rate_limiter',
    'require_twilio_webhook',
    'require_deliverect_webhook',
    'require_webhook_auth',
    'check_webhook_rate_limit',
    'generate_webhook_secret',
    'create_webhook_headers'
]