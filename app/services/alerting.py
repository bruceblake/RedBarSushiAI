"""
Proactive Alerting and Notification System for RedBarSushiAI.

This module provides alerting mechanisms for critical system events
including circuit breaker state changes, performance degradation,
and operational issues.
"""

import asyncio
import json
import logging
import smtplib
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Any, List, Optional, Callable
from enum import Enum
from dataclasses import dataclass, asdict
import aiohttp

from app.config import settings
from app.utils.enhanced_logging import get_logger

logger = get_logger(__name__)

class AlertSeverity(Enum):
    """Alert severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

class AlertType(Enum):
    """Types of alerts in the system."""
    CIRCUIT_BREAKER_OPEN = "circuit_breaker_open"
    CIRCUIT_BREAKER_CLOSED = "circuit_breaker_closed"
    HIGH_LATENCY = "high_latency"
    LOW_CONFIDENCE_PATTERN = "low_confidence_pattern"
    TOOL_CALL_FAILURE = "tool_call_failure"
    HSM_ERROR = "hsm_error"
    PERFORMANCE_DEGRADATION = "performance_degradation"
    SYSTEM_ERROR = "system_error"
    FALLBACK_MODE_ACTIVATED = "fallback_mode_activated"

@dataclass
class Alert:
    """Alert data structure."""
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    message: str
    timestamp: float
    metadata: Dict[str, Any]
    call_sid: Optional[str] = None
    resolved: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary."""
        return {
            **asdict(self),
            "alert_type": self.alert_type.value,
            "severity": self.severity.value,
            "timestamp_iso": datetime.fromtimestamp(self.timestamp).isoformat()
        }

class AlertingService:
    """
    Centralized alerting service for RedBarSushiAI.
    
    Handles multiple notification channels including email, webhooks,
    and structured logging for monitoring systems.
    """
    
    def __init__(self):
        """Initialize the alerting service."""
        self.alert_handlers: List[Callable] = []
        self.alert_history: List[Alert] = []
        self.max_history = 1000  # Keep last 1000 alerts
        
        # Initialize alert handlers based on configuration
        self._initialize_handlers()
        
        logger.info("Alerting service initialized")
    
    def _initialize_handlers(self):
        """Initialize alert handlers based on configuration."""
        # Email handler
        if (hasattr(settings, 'ALERT_EMAIL_ENABLED') and 
            getattr(settings, 'ALERT_EMAIL_ENABLED', False)):
            self.alert_handlers.append(self._send_email_alert)
        
        # Webhook handler
        if (hasattr(settings, 'ALERT_WEBHOOK_URL') and 
            getattr(settings, 'ALERT_WEBHOOK_URL', None)):
            self.alert_handlers.append(self._send_webhook_alert)
        
        # Always include structured logging
        self.alert_handlers.append(self._log_structured_alert)
    
    async def send_alert(self, alert: Alert) -> None:
        """
        Send an alert through all configured channels.
        
        Args:
            alert: Alert to send
        """
        # Add to history
        self.alert_history.append(alert)
        if len(self.alert_history) > self.max_history:
            self.alert_history.pop(0)
        
        # Send through all handlers
        for handler in self.alert_handlers:
            try:
                await handler(alert)
            except Exception as e:
                logger.error(f"Alert handler failed: {e}", exc_info=True)
    
    async def _log_structured_alert(self, alert: Alert) -> None:
        """Log alert as structured JSON for monitoring systems."""
        alert_data = alert.to_dict()
        
        # Add additional context for monitoring
        alert_data.update({
            "service": "redbarsushi-ai",
            "environment": getattr(settings, 'ENVIRONMENT', 'unknown'),
            "log_type": "alert"
        })
        
        # Log with appropriate level based on severity
        if alert.severity in [AlertSeverity.CRITICAL, AlertSeverity.HIGH]:
            logger.critical(f"ALERT: {json.dumps(alert_data)}")
        elif alert.severity == AlertSeverity.MEDIUM:
            logger.warning(f"ALERT: {json.dumps(alert_data)}")
        else:
            logger.info(f"ALERT: {json.dumps(alert_data)}")
    
    async def _send_email_alert(self, alert: Alert) -> None:
        """Send alert via email."""
        try:
            # Email configuration
            smtp_host = getattr(settings, 'ALERT_SMTP_HOST', 'localhost')
            smtp_port = getattr(settings, 'ALERT_SMTP_PORT', 587)
            smtp_user = getattr(settings, 'ALERT_SMTP_USER', '')
            smtp_password = getattr(settings, 'ALERT_SMTP_PASSWORD', '')
            from_email = getattr(settings, 'ALERT_FROM_EMAIL', 'alerts@redbarsushi.com')
            to_emails = getattr(settings, 'ALERT_TO_EMAILS', '').split(',')
            
            if not to_emails or not to_emails[0]:
                logger.warning("No alert email recipients configured")
                return
            
            # Create email message
            msg = MIMEMultipart()
            msg['From'] = from_email
            msg['To'] = ', '.join(to_emails)
            msg['Subject'] = f"🚨 RedBarSushiAI Alert: {alert.title}"
            
            # Email body
            body = f"""
RedBarSushiAI Alert

Alert Type: {alert.alert_type.value}
Severity: {alert.severity.value.upper()}
Time: {datetime.fromtimestamp(alert.timestamp).strftime('%Y-%m-%d %H:%M:%S UTC')}
Call SID: {alert.call_sid or 'N/A'}

Message:
{alert.message}

Metadata:
{json.dumps(alert.metadata, indent=2)}

---
This is an automated alert from RedBarSushiAI monitoring system.
"""
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email
            server = smtplib.SMTP(smtp_host, smtp_port)
            if smtp_user and smtp_password:
                server.starttls()
                server.login(smtp_user, smtp_password)
            
            server.send_message(msg)
            server.quit()
            
            logger.info(f"Alert email sent successfully for {alert.alert_type.value}")
            
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}", exc_info=True)
    
    async def _send_webhook_alert(self, alert: Alert) -> None:
        """Send alert via webhook."""
        try:
            webhook_url = getattr(settings, 'ALERT_WEBHOOK_URL', '')
            webhook_secret = getattr(settings, 'ALERT_WEBHOOK_SECRET', '')
            
            if not webhook_url:
                return
            
            # Prepare webhook payload
            payload = {
                "alert": alert.to_dict(),
                "service": "redbarsushi-ai",
                "environment": getattr(settings, 'ENVIRONMENT', 'unknown')
            }
            
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "RedBarSushiAI/1.0"
            }
            
            if webhook_secret:
                headers["X-Alert-Secret"] = webhook_secret
            
            # Send webhook
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    webhook_url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        logger.info(f"Alert webhook sent successfully for {alert.alert_type.value}")
                    else:
                        logger.warning(f"Webhook returned status {response.status}")
                        
        except Exception as e:
            logger.error(f"Failed to send webhook alert: {e}", exc_info=True)
    
    def get_recent_alerts(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent alerts for monitoring dashboard."""
        recent = self.alert_history[-limit:] if self.alert_history else []
        return [alert.to_dict() for alert in reversed(recent)]
    
    def get_alert_summary(self) -> Dict[str, Any]:
        """Get alert summary statistics."""
        if not self.alert_history:
            return {"total_alerts": 0, "by_severity": {}, "by_type": {}}
        
        # Count by severity
        by_severity = {}
        by_type = {}
        recent_24h = []
        current_time = time.time()
        
        for alert in self.alert_history:
            # Count by severity
            severity = alert.severity.value
            by_severity[severity] = by_severity.get(severity, 0) + 1
            
            # Count by type
            alert_type = alert.alert_type.value
            by_type[alert_type] = by_type.get(alert_type, 0) + 1
            
            # Count recent (24h)
            if current_time - alert.timestamp <= 86400:  # 24 hours
                recent_24h.append(alert)
        
        return {
            "total_alerts": len(self.alert_history),
            "recent_24h": len(recent_24h),
            "by_severity": by_severity,
            "by_type": by_type,
            "last_alert": self.alert_history[-1].to_dict() if self.alert_history else None
        }

# Global alerting service instance
alerting_service = AlertingService()

# Convenience functions for common alerts
async def alert_circuit_breaker_open(metadata: Dict[str, Any], call_sid: Optional[str] = None):
    """Send critical alert when circuit breaker opens."""
    alert = Alert(
        alert_type=AlertType.CIRCUIT_BREAKER_OPEN,
        severity=AlertSeverity.CRITICAL,
        title="OpenAI Circuit Breaker OPEN",
        message="🚨 CRITICAL: OpenAI API circuit breaker has opened. System is now in static fallback mode. "
                "Orders may be affected. Immediate attention required.",
        timestamp=time.time(),
        metadata=metadata,
        call_sid=call_sid
    )
    await alerting_service.send_alert(alert)

async def alert_circuit_breaker_closed(metadata: Dict[str, Any], call_sid: Optional[str] = None):
    """Send info alert when circuit breaker closes (recovery)."""
    alert = Alert(
        alert_type=AlertType.CIRCUIT_BREAKER_CLOSED,
        severity=AlertSeverity.INFO,
        title="OpenAI Circuit Breaker CLOSED",
        message="✅ RECOVERY: OpenAI API circuit breaker has closed. System has recovered and is operating normally.",
        timestamp=time.time(),
        metadata=metadata,
        call_sid=call_sid
    )
    await alerting_service.send_alert(alert)

async def alert_high_latency(latency_ms: float, threshold_ms: float, metadata: Dict[str, Any], call_sid: Optional[str] = None):
    """Send alert for high latency detection."""
    alert = Alert(
        alert_type=AlertType.HIGH_LATENCY,
        severity=AlertSeverity.HIGH,
        title="High Latency Detected",
        message=f"⚠️ HIGH LATENCY: Response time of {latency_ms:.0f}ms exceeded threshold of {threshold_ms:.0f}ms. "
                "User experience may be degraded.",
        timestamp=time.time(),
        metadata={**metadata, "latency_ms": latency_ms, "threshold_ms": threshold_ms},
        call_sid=call_sid
    )
    await alerting_service.send_alert(alert)

async def alert_low_confidence_pattern(confidence: float, threshold: float, metadata: Dict[str, Any], call_sid: Optional[str] = None):
    """Send alert for recurring low confidence patterns."""
    alert = Alert(
        alert_type=AlertType.LOW_CONFIDENCE_PATTERN,
        severity=AlertSeverity.MEDIUM,
        title="Low Confidence Pattern Detected",
        message=f"⚠️ AI CONFIDENCE: Confidence score of {confidence:.2f} below threshold of {threshold:.2f}. "
                "AI may be struggling with user input patterns.",
        timestamp=time.time(),
        metadata={**metadata, "confidence": confidence, "threshold": threshold},
        call_sid=call_sid
    )
    await alerting_service.send_alert(alert)

async def alert_fallback_mode_activated(reason: str, metadata: Dict[str, Any], call_sid: Optional[str] = None):
    """Send alert when static fallback mode is activated."""
    alert = Alert(
        alert_type=AlertType.FALLBACK_MODE_ACTIVATED,
        severity=AlertSeverity.HIGH,
        title="Static Fallback Mode Activated",
        message=f"🔄 FALLBACK: System switched to static fallback mode. Reason: {reason}. "
                "Limited functionality available until AI services recover.",
        timestamp=time.time(),
        metadata={**metadata, "reason": reason},
        call_sid=call_sid
    )
    await alerting_service.send_alert(alert)