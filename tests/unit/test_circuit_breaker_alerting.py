"""
Unit tests for Circuit Breaker and Alerting functionality.

Tests the circuit breaker pattern, alerting system integration,
and metrics logging for production observability.
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from app.services.circuit_breaker import OpenAICircuitBreaker, CircuitBreakerConfig, CircuitState, CircuitBreakerError
from app.services.alerting import AlertingService, Alert, AlertType, AlertSeverity
from app.utils.metrics_logger import MetricsLogger, PerformanceMetric


class TestCircuitBreakerFunctionality:
    """Test suite for Circuit Breaker functionality."""
    
    @pytest.fixture
    def circuit_breaker_config(self):
        """Create a test configuration for circuit breaker."""
        return CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=10,
            success_threshold=2,
            timeout_threshold=5.0,
            monitor_window=60
        )
    
    @pytest.fixture
    def circuit_breaker(self, circuit_breaker_config):
        """Create a circuit breaker instance for testing."""
        return OpenAICircuitBreaker(circuit_breaker_config)
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_closed_state_success(self, circuit_breaker):
        """Test circuit breaker in CLOSED state with successful calls."""
        async def successful_function():
            return "success"
        
        # Execute successful call
        result = await circuit_breaker.call(successful_function)
        
        # Verify success
        assert result == "success"
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.success_count == 1
        assert circuit_breaker.failure_count == 0
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_failure_accumulation(self, circuit_breaker):
        """Test that failures accumulate and trigger circuit opening."""
        async def failing_function():
            raise Exception("OpenAI API error")
        
        # Execute failures below threshold
        for i in range(2):
            with pytest.raises(Exception):
                await circuit_breaker.call(failing_function)
            assert circuit_breaker.state == CircuitState.CLOSED
        
        # One more failure should open the circuit
        with pytest.raises(Exception):
            await circuit_breaker.call(failing_function)
        
        assert circuit_breaker.state == CircuitState.OPEN
        assert len(circuit_breaker.recent_failures) == 3
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_open_state_fast_fail(self, circuit_breaker):
        """Test that OPEN circuit breaker fails fast."""
        # Force circuit to OPEN state
        circuit_breaker.state = CircuitState.OPEN
        circuit_breaker.last_failure_time = time.time()
        
        async def dummy_function():
            return "should not execute"
        
        # Should fail fast without executing function
        with pytest.raises(CircuitBreakerError) as exc_info:
            await circuit_breaker.call(dummy_function)
        
        assert "Circuit breaker is OPEN" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_half_open_recovery(self, circuit_breaker):
        """Test circuit breaker recovery through HALF_OPEN state."""
        # Force circuit to OPEN state
        circuit_breaker.state = CircuitState.OPEN
        circuit_breaker.last_failure_time = time.time() - 15  # Past recovery timeout
        
        async def successful_function():
            return "recovery success"
        
        # First call should transition to HALF_OPEN and succeed
        result = await circuit_breaker.call(successful_function)
        assert result == "recovery success"
        assert circuit_breaker.state == CircuitState.HALF_OPEN
        
        # Second successful call should close the circuit
        result = await circuit_breaker.call(successful_function)
        assert result == "recovery success"
        assert circuit_breaker.state == CircuitState.CLOSED
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_half_open_failure(self, circuit_breaker):
        """Test that failure in HALF_OPEN state returns to OPEN."""
        # Set to HALF_OPEN state
        circuit_breaker.state = CircuitState.HALF_OPEN
        circuit_breaker.last_failure_time = time.time() - 15
        
        async def failing_function():
            raise Exception("Still failing")
        
        # Failure in HALF_OPEN should return to OPEN
        with pytest.raises(Exception):
            await circuit_breaker.call(failing_function)
        
        assert circuit_breaker.state == CircuitState.OPEN
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_alerting_integration(self, circuit_breaker):
        """Test that circuit breaker state changes trigger alerts."""
        with patch.object(circuit_breaker, '_send_circuit_breaker_alert') as mock_alert:
            # Trigger circuit opening
            async def failing_function():
                raise Exception("Failure")
            
            # Accumulate failures to open circuit
            for _ in range(3):
                with pytest.raises(Exception):
                    await circuit_breaker.call(failing_function)
            
            # Verify alert was sent for opening
            mock_alert.assert_called_with("OPEN", "closed")
    
    def test_circuit_breaker_status_reporting(self, circuit_breaker):
        """Test circuit breaker status reporting."""
        status = circuit_breaker.status
        
        required_fields = [
            "state", "failure_count", "success_count", "recent_failures",
            "last_failure_time", "last_state_change", "uptime_since_last_change"
        ]
        
        for field in required_fields:
            assert field in status
        
        assert status["state"] == "closed"
        assert isinstance(status["uptime_since_last_change"], float)
    
    def test_sliding_window_failure_cleanup(self, circuit_breaker):
        """Test that old failures are cleaned up from sliding window."""
        current_time = time.time()
        
        # Add old failures (outside window)
        circuit_breaker.recent_failures = [
            current_time - 120,  # 2 minutes ago (outside 1 min window)
            current_time - 90,   # 1.5 minutes ago (outside window)
            current_time - 30    # 30 seconds ago (inside window)
        ]
        
        # Clean old failures
        circuit_breaker._clean_old_failures()
        
        # Only recent failure should remain
        assert len(circuit_breaker.recent_failures) == 1
        assert circuit_breaker.recent_failures[0] == current_time - 30


class TestAlertingSystemFunctionality:
    """Test suite for Alerting System functionality."""
    
    @pytest.fixture
    def alerting_service(self):
        """Create an alerting service for testing."""
        return AlertingService()
    
    @pytest.fixture
    def test_alert(self):
        """Create a test alert."""
        return Alert(
            alert_type=AlertType.CIRCUIT_BREAKER_OPEN,
            severity=AlertSeverity.CRITICAL,
            title="Test Circuit Breaker Alert",
            message="Test message for circuit breaker opening",
            timestamp=time.time(),
            metadata={"test": True},
            call_sid="test_call_123"
        )
    
    @pytest.mark.asyncio
    async def test_alert_structured_logging(self, alerting_service, test_alert):
        """Test that alerts are logged as structured JSON."""
        with patch.object(alerting_service, '_log_structured_alert') as mock_log:
            await alerting_service.send_alert(test_alert)
            
            mock_log.assert_called_once_with(test_alert)
    
    @pytest.mark.asyncio
    async def test_alert_history_management(self, alerting_service, test_alert):
        """Test alert history tracking and limits."""
        # Send multiple alerts
        for i in range(5):
            alert = Alert(
                alert_type=AlertType.HIGH_LATENCY,
                severity=AlertSeverity.MEDIUM,
                title=f"Test Alert {i}",
                message=f"Test message {i}",
                timestamp=time.time(),
                metadata={"index": i}
            )
            await alerting_service.send_alert(alert)
        
        # Verify alerts are tracked
        assert len(alerting_service.alert_history) == 5
        
        # Test history limit (set max_history to small value for testing)
        alerting_service.max_history = 3
        
        # Add more alerts
        for i in range(3):
            await alerting_service.send_alert(test_alert)
        
        # Should only keep last 3
        assert len(alerting_service.alert_history) == 3
    
    def test_alert_summary_statistics(self, alerting_service):
        """Test alert summary generation."""
        # Add test alerts
        alerts = [
            Alert(AlertType.CIRCUIT_BREAKER_OPEN, AlertSeverity.CRITICAL, "Test 1", "Msg 1", time.time(), {}),
            Alert(AlertType.HIGH_LATENCY, AlertSeverity.HIGH, "Test 2", "Msg 2", time.time(), {}),
            Alert(AlertType.HIGH_LATENCY, AlertSeverity.HIGH, "Test 3", "Msg 3", time.time(), {}),
            Alert(AlertType.LOW_CONFIDENCE_PATTERN, AlertSeverity.MEDIUM, "Test 4", "Msg 4", time.time(), {})
        ]
        
        alerting_service.alert_history = alerts
        
        summary = alerting_service.get_alert_summary()
        
        assert summary["total_alerts"] == 4
        assert summary["by_severity"]["critical"] == 1
        assert summary["by_severity"]["high"] == 2
        assert summary["by_severity"]["medium"] == 1
        assert summary["by_type"]["high_latency"] == 2
        assert summary["by_type"]["circuit_breaker_open"] == 1
    
    def test_recent_alerts_retrieval(self, alerting_service):
        """Test retrieval of recent alerts."""
        # Add test alerts with timestamps
        current_time = time.time()
        alerts = []
        
        for i in range(10):
            alert = Alert(
                alert_type=AlertType.SYSTEM_ERROR,
                severity=AlertSeverity.INFO,
                title=f"Alert {i}",
                message=f"Message {i}",
                timestamp=current_time - i * 60,  # 1 minute apart
                metadata={"index": i}
            )
            alerts.append(alert)
        
        alerting_service.alert_history = alerts
        
        # Get recent alerts (limit 5)
        recent = alerting_service.get_recent_alerts(5)
        
        assert len(recent) == 5
        # Should be in reverse chronological order (most recent first)
        assert recent[0]["metadata"]["index"] == 0  # Most recent
        assert recent[4]["metadata"]["index"] == 4  # 5th most recent
    
    @pytest.mark.asyncio
    async def test_email_alert_configuration(self, alerting_service):
        """Test email alert configuration and sending."""
        with patch('smtplib.SMTP') as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server
            
            # Mock settings for email
            with patch('app.services.alerting.settings') as mock_settings:
                mock_settings.ALERT_EMAIL_ENABLED = True
                mock_settings.ALERT_SMTP_HOST = "smtp.test.com"
                mock_settings.ALERT_SMTP_PORT = 587
                mock_settings.ALERT_TO_EMAILS = "test@example.com"
                mock_settings.ALERT_FROM_EMAIL = "alerts@test.com"
                
                # Initialize service with email handler
                service = AlertingService()
                service.alert_handlers = [service._send_email_alert]
                
                test_alert = Alert(
                    alert_type=AlertType.CIRCUIT_BREAKER_OPEN,
                    severity=AlertSeverity.CRITICAL,
                    title="Test Email Alert",
                    message="Test email message",
                    timestamp=time.time(),
                    metadata={}
                )
                
                await service.send_alert(test_alert)
                
                # Verify SMTP was called
                mock_smtp.assert_called_once()
                mock_server.send_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_webhook_alert_sending(self, alerting_service):
        """Test webhook alert sending."""
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = MagicMock()
            mock_response.status = 200
            
            mock_post = AsyncMock()
            mock_post.__aenter__.return_value = mock_response
            
            mock_session_instance = MagicMock()
            mock_session_instance.post.return_value = mock_post
            mock_session.return_value.__aenter__.return_value = mock_session_instance
            
            # Mock settings for webhook
            with patch('app.services.alerting.settings') as mock_settings:
                mock_settings.ALERT_WEBHOOK_URL = "https://webhook.test.com/alerts"
                mock_settings.ALERT_WEBHOOK_SECRET = "secret123"
                
                # Initialize service with webhook handler
                service = AlertingService()
                service.alert_handlers = [service._send_webhook_alert]
                
                test_alert = Alert(
                    alert_type=AlertType.HIGH_LATENCY,
                    severity=AlertSeverity.HIGH,
                    title="Test Webhook Alert",
                    message="Test webhook message",
                    timestamp=time.time(),
                    metadata={}
                )
                
                await service.send_alert(test_alert)
                
                # Verify webhook was called
                mock_session_instance.post.assert_called_once()


class TestMetricsLoggingFunctionality:
    """Test suite for Metrics Logging functionality."""
    
    @pytest.fixture
    def metrics_logger(self):
        """Create a metrics logger for testing."""
        return MetricsLogger()
    
    def test_performance_metric_creation(self):
        """Test creation of performance metrics."""
        metric = PerformanceMetric(
            metric_type="test_metric",
            value=123.45,
            unit="milliseconds",
            timestamp=time.time(),
            call_sid="test_call",
            metadata={"test": True}
        )
        
        metric_dict = metric.to_dict()
        
        assert metric_dict["metric_type"] == "test_metric"
        assert metric_dict["value"] == 123.45
        assert metric_dict["unit"] == "milliseconds"
        assert metric_dict["call_sid"] == "test_call"
        assert "timestamp_iso" in metric_dict
        assert metric_dict["service"] == "redbarsushi-ai"
        assert metric_dict["log_type"] == "metric"
    
    def test_intent_confidence_logging(self, metrics_logger):
        """Test intent confidence metric logging."""
        with patch.object(metrics_logger, 'log_metric') as mock_log:
            metrics_logger.log_intent_confidence(
                confidence=0.85,
                intent="add_item",
                call_sid="test_call",
                metadata={"state": "ordering"}
            )
            
            mock_log.assert_called_once()
            metric = mock_log.call_args[0][0]
            
            assert metric.metric_type == "intent_confidence_score"
            assert metric.value == 0.85
            assert metric.unit == "ratio"
            assert metric.call_sid == "test_call"
            assert metric.metadata["intent"] == "add_item"
            assert metric.metadata["state"] == "ordering"
    
    def test_tool_call_latency_logging(self, metrics_logger):
        """Test tool call latency metric logging."""
        with patch.object(metrics_logger, 'log_metric') as mock_log:
            metrics_logger.log_tool_call_latency(
                latency_ms=250.5,
                tool_name="menu_search",
                call_sid="test_call",
                metadata={"items_found": 3}
            )
            
            mock_log.assert_called_once()
            metric = mock_log.call_args[0][0]
            
            assert metric.metric_type == "tool_call_latency"
            assert metric.value == 250.5
            assert metric.unit == "milliseconds"
            assert metric.metadata["tool_name"] == "menu_search"
            assert metric.metadata["items_found"] == 3
    
    def test_hsm_state_transition_logging(self, metrics_logger):
        """Test HSM state transition metric logging."""
        with patch.object(metrics_logger, 'log_metric') as mock_log:
            metrics_logger.log_hsm_state_transition(
                from_state="ORDERING",
                to_state="VALIDATION",
                duration_ms=50.0,
                call_sid="test_call"
            )
            
            mock_log.assert_called_once()
            metric = mock_log.call_args[0][0]
            
            assert metric.metric_type == "hsm_state_transition"
            assert metric.value == 50.0
            assert metric.unit == "milliseconds"
            assert metric.metadata["from_state"] == "ORDERING"
            assert metric.metadata["to_state"] == "VALIDATION"
    
    def test_circuit_breaker_state_change_logging(self, metrics_logger):
        """Test circuit breaker state change metric logging."""
        with patch.object(metrics_logger, 'log_metric') as mock_log:
            metrics_logger.log_circuit_breaker_state_change(
                from_state="closed",
                to_state="open",
                failure_count=5
            )
            
            mock_log.assert_called_once()
            metric = mock_log.call_args[0][0]
            
            assert metric.metric_type == "circuit_breaker_state_change"
            assert metric.value == 5
            assert metric.unit == "count"
            assert metric.metadata["from_state"] == "closed"
            assert metric.metadata["to_state"] == "open"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])