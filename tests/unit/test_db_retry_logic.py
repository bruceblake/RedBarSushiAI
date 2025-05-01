"""
Test the database retry logic implemented in db_init.py
"""
import os
import pytest
from unittest.mock import patch, MagicMock, call
from app.db_init import execute_with_retry, verify_connection


class TestDatabaseRetryLogic:
    """Test cases for the database connection retry logic."""

    def test_verify_connection_success(self):
        """Test that verify_connection returns True when connection is successful."""
        # Mock the session connection to return success
        mock_conn = MagicMock()
        mock_conn.execute.return_value.scalar.return_value = 1
        
        mock_session = MagicMock()
        mock_session.connection.return_value.__enter__.return_value = mock_conn
        
        with patch('app.db_init.db.session', mock_session):
            assert verify_connection() is True
            mock_conn.execute.assert_called_once()

    def test_verify_connection_failure(self):
        """Test that verify_connection returns False when connection fails."""
        # Mock the session connection to raise an exception
        mock_session = MagicMock()
        mock_session.connection.side_effect = Exception("Connection error")
        
        with patch('app.db_init.db.session', mock_session):
            assert verify_connection() is False

    def test_execute_with_retry_success_first_attempt(self):
        """Test that execute_with_retry succeeds on the first attempt."""
        # Create a mock function that succeeds
        mock_func = MagicMock(return_value="success")
        
        # Execute with retry
        with patch('app.db_init.verify_connection', return_value=True):
            result = execute_with_retry(mock_func, "arg1", keyword_arg="value")
        
        # Verify function was called exactly once with correct arguments
        assert result == "success"
        mock_func.assert_called_once_with("arg1", keyword_arg="value")

    def test_execute_with_retry_success_after_failures(self):
        """Test that execute_with_retry succeeds after several failures."""
        # Create a mock function that fails twice then succeeds
        mock_func = MagicMock(side_effect=[
            Exception("Failure 1"),
            Exception("Failure 2"),
            "success"
        ])
        
        # Execute with retry, mocking time.sleep to avoid actual delays
        with patch('app.db_init.time.sleep'), \
             patch('app.db_init.verify_connection', return_value=True), \
             patch('app.db_init.db.session'):
            result = execute_with_retry(mock_func)
        
        # Verify function was called exactly three times
        assert result == "success"
        assert mock_func.call_count == 3

    def test_execute_with_retry_all_attempts_fail(self):
        """Test that execute_with_retry returns None when all attempts fail."""
        # Override environment variables for testing
        with patch.dict(os.environ, {"DB_MAX_RETRIES": "3"}):
            # Create a mock function that always fails
            mock_func = MagicMock(side_effect=Exception("Always fails"))
            
            # Execute with retry, mocking time.sleep to avoid actual delays
            with patch('app.db_init.time.sleep'), \
                 patch('app.db_init.verify_connection', return_value=True), \
                 patch('app.db_init.db.session'):
                result = execute_with_retry(mock_func)
            
            # Verify function was called exactly three times
            assert result is None
            assert mock_func.call_count == 3

    def test_execute_with_retry_backoff_timing(self):
        """Test that execute_with_retry uses correct backoff timing."""
        # Override environment variables for testing
        with patch.dict(os.environ, {
            "DB_MAX_RETRIES": "3",
            "DB_INITIAL_RETRY_DELAY": "1.0",
            "DB_MAX_RETRY_DELAY": "10.0"
        }):
            # Create a mock function that always fails
            mock_func = MagicMock(side_effect=Exception("Always fails"))
            
            # Execute with retry, capturing sleep calls
            mock_sleep = MagicMock()
            with patch('app.db_init.time.sleep', mock_sleep), \
                 patch('app.db_init.random.uniform', return_value=0.1), \
                 patch('app.db_init.verify_connection', return_value=True), \
                 patch('app.db_init.db.session'):
                result = execute_with_retry(mock_func)
            
            # Verify backoff delay pattern (1*2^0 + 0.1, 1*2^1 + 0.1)
            assert result is None
            assert mock_sleep.call_count == 2  # 3 attempts = 2 sleeps
            expected_calls = [
                call(1.1),  # Initial delay + jitter
                call(2.1),  # Second delay + jitter
            ]
            mock_sleep.assert_has_calls(expected_calls)

    def test_execute_with_retry_non_db_error(self):
        """Test that execute_with_retry doesn't retry for non-database errors."""
        # Create a mock function that raises a KeyError (not a DB error)
        mock_func = MagicMock(side_effect=KeyError("Not a DB error"))
        
        # Execute with retry should re-raise the KeyError
        with patch('app.db_init.time.sleep'), \
             patch('app.db_init.verify_connection', return_value=True), \
             patch('app.db_init.db.session'), \
             pytest.raises(KeyError):
            execute_with_retry(mock_func)
        
        # Verify function was called exactly once
        mock_func.assert_called_once()