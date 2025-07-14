"""
Monitoring and Alerting API endpoints for RedBarSushiAI.

Provides endpoints for checking system health, metrics, alerts,
and circuit breaker status.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
import time

from app.services.alerting import alerting_service
from app.services.circuit_breaker import get_circuit_breaker
from app.config import settings

router = APIRouter(prefix="/monitoring", tags=["monitoring"])

@router.get("/health")
async def get_health_status() -> Dict[str, Any]:
    """
    Get overall system health status.
    
    Returns:
        Health status with key system indicators
    """
    circuit_breaker = get_circuit_breaker()
    
    return {
        "status": "healthy" if not circuit_breaker.is_open else "degraded",
        "timestamp": time.time(),
        "circuit_breaker": circuit_breaker.status,
        "service": "redbarsushi-ai",
        "version": "1.0.0"
    }

@router.get("/alerts")
async def get_recent_alerts(limit: int = 50) -> Dict[str, Any]:
    """
    Get recent alerts from the system.
    
    Args:
        limit: Maximum number of alerts to return
        
    Returns:
        Recent alerts and summary statistics
    """
    if limit > 500:
        raise HTTPException(status_code=400, detail="Limit cannot exceed 500")
    
    recent_alerts = alerting_service.get_recent_alerts(limit)
    alert_summary = alerting_service.get_alert_summary()
    
    return {
        "alerts": recent_alerts,
        "summary": alert_summary,
        "timestamp": time.time()
    }

@router.get("/alerts/summary")
async def get_alert_summary() -> Dict[str, Any]:
    """
    Get alert summary statistics.
    
    Returns:
        Alert summary with counts by severity and type
    """
    return alerting_service.get_alert_summary()

@router.get("/circuit-breaker")
async def get_circuit_breaker_status() -> Dict[str, Any]:
    """
    Get circuit breaker status and configuration.
    
    Returns:
        Circuit breaker state and metrics
    """
    circuit_breaker = get_circuit_breaker()
    
    return {
        "status": circuit_breaker.status,
        "configuration": {
            "failure_threshold": circuit_breaker.config.failure_threshold,
            "recovery_timeout": circuit_breaker.config.recovery_timeout,
            "success_threshold": circuit_breaker.config.success_threshold,
            "timeout_threshold": circuit_breaker.config.timeout_threshold,
            "monitor_window": circuit_breaker.config.monitor_window
        },
        "timestamp": time.time()
    }

@router.get("/metrics/config")
async def get_metrics_configuration() -> Dict[str, Any]:
    """
    Get current monitoring and alerting configuration.
    
    Returns:
        Configuration values for monitoring thresholds
    """
    return {
        "confidence_thresholds": {
            "global_command": settings.GLOBAL_COMMAND_CONFIDENCE_THRESHOLD,
            "order_completion": settings.ORDER_COMPLETION_CONFIDENCE_THRESHOLD,
            "order_modification": settings.ORDER_MODIFICATION_CONFIDENCE_THRESHOLD,
            "menu_search": settings.MENU_SEARCH_CONFIDENCE_THRESHOLD,
            "partial_transcript": settings.PARTIAL_TRANSCRIPT_CONFIDENCE_THRESHOLD,
            "low_confidence_alert": settings.LOW_CONFIDENCE_ALERT_THRESHOLD
        },
        "performance_thresholds": {
            "high_latency_ms": settings.HIGH_LATENCY_THRESHOLD_MS
        },
        "circuit_breaker": {
            "failure_threshold": settings.CIRCUIT_BREAKER_FAILURE_THRESHOLD,
            "recovery_timeout": settings.CIRCUIT_BREAKER_RECOVERY_TIMEOUT,
            "success_threshold": settings.CIRCUIT_BREAKER_SUCCESS_THRESHOLD
        },
        "alerting": {
            "email_enabled": settings.ALERT_EMAIL_ENABLED,
            "webhook_configured": bool(settings.ALERT_WEBHOOK_URL)
        },
        "timestamp": time.time()
    }

@router.post("/test-alert")
async def trigger_test_alert() -> Dict[str, Any]:
    """
    Trigger a test alert to verify alerting system.
    
    Returns:
        Confirmation of test alert sent
    """
    from app.services.alerting import Alert, AlertType, AlertSeverity
    
    test_alert = Alert(
        alert_type=AlertType.SYSTEM_ERROR,
        severity=AlertSeverity.INFO,
        title="Test Alert",
        message="This is a test alert to verify the alerting system is working correctly.",
        timestamp=time.time(),
        metadata={
            "test": True,
            "triggered_by": "monitoring_api"
        }
    )
    
    await alerting_service.send_alert(test_alert)
    
    return {
        "message": "Test alert sent successfully",
        "alert_id": f"test_{int(time.time())}",
        "timestamp": time.time()
    }

@router.get("/dashboard")
async def get_dashboard_data() -> Dict[str, Any]:
    """
    Get comprehensive dashboard data for monitoring.
    
    Returns:
        Combined data for monitoring dashboard
    """
    circuit_breaker = get_circuit_breaker()
    alert_summary = alerting_service.get_alert_summary()
    recent_alerts = alerting_service.get_recent_alerts(10)
    
    # Calculate uptime
    uptime_since_last_change = time.time() - circuit_breaker.status["last_state_change"]
    
    return {
        "system_status": {
            "overall": "healthy" if not circuit_breaker.is_open else "degraded",
            "circuit_breaker_state": circuit_breaker.status["state"],
            "uptime_hours": uptime_since_last_change / 3600
        },
        "alerts": {
            "recent_count": len(recent_alerts),
            "critical_24h": len([a for a in recent_alerts if a.get("severity") == "critical"]),
            "summary": alert_summary
        },
        "circuit_breaker": circuit_breaker.status,
        "thresholds": {
            "high_latency_ms": settings.HIGH_LATENCY_THRESHOLD_MS,
            "low_confidence": settings.LOW_CONFIDENCE_ALERT_THRESHOLD
        },
        "timestamp": time.time()
    }

@router.get("/partial-transcripts")
async def get_partial_transcript_status() -> Dict[str, Any]:
    """
    Get status of partial transcript processing.
    
    Returns:
        Status of pending partial transcripts and processor configuration
    """
    from app.utils.partial_transcript_processor import get_partial_processor
    
    processor = get_partial_processor()
    
    # Clean up stale transcripts before reporting
    processor.cleanup_stale_pending_transcripts()
    
    return {
        "pending_status": processor.get_pending_status(),
        "configuration": {
            "confidence_threshold": processor.confidence_threshold,
            "delay_ms": processor.delay_ms,
            "end_of_speech_threshold": processor.end_of_speech_threshold
        },
        "timestamp": time.time()
    }