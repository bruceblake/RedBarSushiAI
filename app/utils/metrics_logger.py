"""
Structured Metrics Logging for RedBarSushiAI.

This module provides structured logging for key performance indicators (KPIs)
to enable monitoring, dashboarding, and performance analysis.
"""

import json
import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict

from app.config import settings
from app.utils.enhanced_logging import get_logger

logger = get_logger(__name__)

@dataclass
class PerformanceMetric:
    """Performance metric data structure."""
    metric_type: str
    value: float
    unit: str
    timestamp: float
    call_sid: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metric to dictionary for JSON logging."""
        return {
            **asdict(self),
            "timestamp_iso": datetime.fromtimestamp(self.timestamp).isoformat(),
            "service": "redbarsushi-ai",
            "environment": getattr(settings, 'ENVIRONMENT', 'unknown'),
            "log_type": "metric"
        }

class MetricsLogger:
    """
    Centralized metrics logging for performance monitoring.
    
    Logs structured JSON metrics that can be consumed by monitoring
    systems like Datadog, Grafana, or CloudWatch.
    """
    
    def __init__(self):
        """Initialize the metrics logger."""
        self.logger = get_logger(f"{__name__}.metrics")
    
    def log_metric(self, metric: PerformanceMetric) -> None:
        """
        Log a performance metric as structured JSON.
        
        Args:
            metric: Performance metric to log
        """
        metric_data = metric.to_dict()
        self.logger.info(f"METRIC: {json.dumps(metric_data)}")
    
    def log_intent_confidence(
        self, 
        confidence: float, 
        intent: str, 
        call_sid: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log intent confidence score."""
        metric = PerformanceMetric(
            metric_type="intent_confidence_score",
            value=confidence,
            unit="ratio",
            timestamp=time.time(),
            call_sid=call_sid,
            metadata={**(metadata or {}), "intent": intent}
        )
        self.log_metric(metric)
    
    def log_tool_call_latency(
        self,
        latency_ms: float,
        tool_name: str,
        call_sid: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log tool call latency."""
        metric = PerformanceMetric(
            metric_type="tool_call_latency",
            value=latency_ms,
            unit="milliseconds",
            timestamp=time.time(),
            call_sid=call_sid,
            metadata={**(metadata or {}), "tool_name": tool_name}
        )
        self.log_metric(metric)
    
    def log_hsm_state_transition(
        self,
        from_state: str,
        to_state: str,
        duration_ms: float,
        call_sid: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log HSM state transition timing."""
        metric = PerformanceMetric(
            metric_type="hsm_state_transition",
            value=duration_ms,
            unit="milliseconds",
            timestamp=time.time(),
            call_sid=call_sid,
            metadata={
                **(metadata or {}),
                "from_state": from_state,
                "to_state": to_state
            }
        )
        self.log_metric(metric)
    
    def log_circuit_breaker_state_change(
        self,
        from_state: str,
        to_state: str,
        failure_count: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log circuit breaker state changes."""
        metric = PerformanceMetric(
            metric_type="circuit_breaker_state_change",
            value=failure_count,
            unit="count",
            timestamp=time.time(),
            metadata={
                **(metadata or {}),
                "from_state": from_state,
                "to_state": to_state
            }
        )
        self.log_metric(metric)
    
    def log_response_latency(
        self,
        latency_ms: float,
        agent_type: str,
        call_sid: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log agent response latency."""
        metric = PerformanceMetric(
            metric_type="response_latency",
            value=latency_ms,
            unit="milliseconds",
            timestamp=time.time(),
            call_sid=call_sid,
            metadata={**(metadata or {}), "agent_type": agent_type}
        )
        self.log_metric(metric)
    
    def log_openai_api_latency(
        self,
        latency_ms: float,
        model: str,
        call_sid: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log OpenAI API call latency."""
        metric = PerformanceMetric(
            metric_type="openai_api_latency",
            value=latency_ms,
            unit="milliseconds",
            timestamp=time.time(),
            call_sid=call_sid,
            metadata={**(metadata or {}), "model": model}
        )
        self.log_metric(metric)
    
    def log_partial_transcript_processing(
        self,
        confidence: float,
        intent: str,
        processing_time_ms: float,
        call_sid: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log partial transcript processing metrics."""
        metric = PerformanceMetric(
            metric_type="partial_transcript_processing",
            value=processing_time_ms,
            unit="milliseconds",
            timestamp=time.time(),
            call_sid=call_sid,
            metadata={
                **(metadata or {}),
                "confidence": confidence,
                "intent": intent
            }
        )
        self.log_metric(metric)
    
    def log_menu_search_performance(
        self,
        search_time_ms: float,
        results_count: int,
        query: str,
        call_sid: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log menu search performance."""
        metric = PerformanceMetric(
            metric_type="menu_search_performance",
            value=search_time_ms,
            unit="milliseconds",
            timestamp=time.time(),
            call_sid=call_sid,
            metadata={
                **(metadata or {}),
                "results_count": results_count,
                "query": query[:50]  # Truncate for privacy
            }
        )
        self.log_metric(metric)
    
    def log_conversation_duration(
        self,
        duration_seconds: float,
        call_sid: str,
        final_state: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log total conversation duration."""
        metric = PerformanceMetric(
            metric_type="conversation_duration",
            value=duration_seconds,
            unit="seconds",
            timestamp=time.time(),
            call_sid=call_sid,
            metadata={
                **(metadata or {}),
                "final_state": final_state
            }
        )
        self.log_metric(metric)
    
    def log_error_rate(
        self,
        error_count: int,
        total_requests: int,
        time_window_minutes: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log error rate metrics."""
        error_rate = error_count / total_requests if total_requests > 0 else 0
        metric = PerformanceMetric(
            metric_type="error_rate",
            value=error_rate,
            unit="ratio",
            timestamp=time.time(),
            metadata={
                **(metadata or {}),
                "error_count": error_count,
                "total_requests": total_requests,
                "time_window_minutes": time_window_minutes
            }
        )
        self.log_metric(metric)

# Global metrics logger instance
metrics_logger = MetricsLogger()

# Convenience functions for common metrics
def log_intent_confidence(confidence: float, intent: str, call_sid: Optional[str] = None, **kwargs):
    """Log intent confidence score."""
    metrics_logger.log_intent_confidence(confidence, intent, call_sid, kwargs)

def log_tool_call_latency(latency_ms: float, tool_name: str, call_sid: Optional[str] = None, **kwargs):
    """Log tool call latency."""
    metrics_logger.log_tool_call_latency(latency_ms, tool_name, call_sid, kwargs)

def log_response_latency(latency_ms: float, agent_type: str, call_sid: Optional[str] = None, **kwargs):
    """Log agent response latency."""
    metrics_logger.log_response_latency(latency_ms, agent_type, call_sid, kwargs)

def log_hsm_state_transition(from_state: str, to_state: str, duration_ms: float, call_sid: Optional[str] = None, **kwargs):
    """Log HSM state transition timing."""
    metrics_logger.log_hsm_state_transition(from_state, to_state, duration_ms, call_sid, kwargs)

def log_circuit_breaker_state_change(from_state: str, to_state: str, failure_count: int, **kwargs):
    """Log circuit breaker state changes."""
    metrics_logger.log_circuit_breaker_state_change(from_state, to_state, failure_count, kwargs)