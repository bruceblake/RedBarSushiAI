"""
Enhanced logging configuration for RedBarSushiAI.

This module provides extensive logging configuration for debugging the system,
particularly focusing on WebSocket connections, voice processing, and
real-time audio streaming.
"""

import logging
import logging.handlers
import os
import sys
import json
import traceback
import time
from datetime import datetime
import uuid

# Create loggers
root_logger = logging.getLogger()
voice_logger = logging.getLogger('voice')
ws_logger = logging.getLogger('websocket')
stream_logger = logging.getLogger('stream')
twilio_logger = logging.getLogger('twilio')
openai_logger = logging.getLogger('openai')
db_logger = logging.getLogger('database')
redis_logger = logging.getLogger('redis')
agent_logger = logging.getLogger('agent')

# Log levels dictionary for easy conversion from strings
LOG_LEVELS = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL
}

# Configure the detailed format for logs
DETAILED_FORMAT = logging.Formatter(
    '%(asctime)s.%(msecs)03d [%(levelname)s] [%(name)s:%(funcName)s:%(lineno)d] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Generate log directories if they don't exist
def ensure_log_dirs():
    log_dir = os.environ.get('LOG_DIR', 'logs')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Create subdirectories for different log types
    for subdir in ['voice', 'websocket', 'stream', 'twilio', 'openai', 'database', 'agent']:
        subdir_path = os.path.join(log_dir, subdir)
        if not os.path.exists(subdir_path):
            os.makedirs(subdir_path)
    
    return log_dir

# Configure file handlers for different components
def setup_file_handlers(log_dir):
    # Root logger file handler
    root_file_handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, 'app.log'),
        maxBytes=10485760,  # 10MB
        backupCount=10
    )
    root_file_handler.setFormatter(DETAILED_FORMAT)
    root_logger.addHandler(root_file_handler)
    
    # Component-specific handlers
    components = {
        'voice': voice_logger,
        'websocket': ws_logger,
        'stream': stream_logger,
        'twilio': twilio_logger,
        'openai': openai_logger,
        'database': db_logger,
        'agent': agent_logger
    }
    
    for name, logger in components.items():
        file_handler = logging.handlers.RotatingFileHandler(
            os.path.join(log_dir, name, f'{name}.log'),
            maxBytes=10485760,  # 10MB
            backupCount=5
        )
        file_handler.setFormatter(DETAILED_FORMAT)
        logger.addHandler(file_handler)

# Configure console logging
def setup_console_logging():
    console_handler = logging.StreamHandler(sys.stdout)
    console_format = logging.Formatter(
        '%(asctime)s [%(levelname)s] [%(name)s] - %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(console_format)
    root_logger.addHandler(console_handler)

# Set up logging levels based on environment variables or defaults
def configure_log_levels():
    # Default log levels
    default_levels = {
        '': 'INFO',           # Root logger
        'voice': 'DEBUG',     # Voice processing
        'websocket': 'DEBUG', # WebSocket connections
        'stream': 'DEBUG',    # Audio streaming
        'twilio': 'DEBUG',    # Twilio integration
        'openai': 'DEBUG',    # OpenAI API calls
        'database': 'INFO',   # Database operations
        'agent': 'DEBUG',     # Agent interactions
        'urllib3': 'WARNING', # Suppress noisy HTTP client
        'werkzeug': 'WARNING' # Suppress noisy WSGI logs
    }
    
    # Environment variable overrides
    for logger_name, default_level in default_levels.items():
        env_var = f"LOG_LEVEL_{logger_name.upper()}" if logger_name else "LOG_LEVEL"
        level_name = os.environ.get(env_var, default_level)
        level = LOG_LEVELS.get(level_name, logging.INFO)
        
        if logger_name:
            logging.getLogger(logger_name).setLevel(level)
        else:
            root_logger.setLevel(level)

# Special filters for focused logging
class CallSidFilter(logging.Filter):
    """Filter logs to include only those with a specific CallSid."""
    
    def __init__(self, call_sid):
        super().__init__()
        self.call_sid = call_sid
    
    def filter(self, record):
        if not hasattr(record, 'call_sid'):
            return False
        return record.call_sid == self.call_sid

# Function to create a session logger for a specific call
def get_session_logger(call_sid):
    """Get a logger dedicated to a specific call session."""
    logger = logging.getLogger(f'session.{call_sid}')
    
    # If this is the first request for this logger, set it up
    if not logger.handlers:
        # Create a file handler specific to this session
        log_dir = ensure_log_dirs()
        session_log_path = os.path.join(log_dir, 'sessions', f'{call_sid}.log')
        
        # Make sure the directory exists
        os.makedirs(os.path.dirname(session_log_path), exist_ok=True)
        
        # Create and configure the handler
        handler = logging.FileHandler(session_log_path)
        handler.setFormatter(DETAILED_FORMAT)
        logger.addHandler(handler)
        
        # Also add a filter to the voice, websocket and stream loggers
        # so they capture events for this call in the dedicated log
        for component_logger in [voice_logger, ws_logger, stream_logger]:
            session_handler = logging.FileHandler(session_log_path)
            session_handler.setFormatter(DETAILED_FORMAT)
            session_handler.addFilter(CallSidFilter(call_sid))
            component_logger.addHandler(session_handler)
    
    return logger

# Initialize the logging system
def initialize_logging():
    """Set up the enhanced logging system."""
    # Clear existing handlers to avoid duplicates
    for logger in [root_logger, voice_logger, ws_logger, stream_logger, 
                  twilio_logger, openai_logger, db_logger, agent_logger]:
        logger.handlers.clear()
    
    # Create log directories
    log_dir = ensure_log_dirs()
    
    # Set up handlers
    setup_file_handlers(log_dir)
    setup_console_logging()
    
    # Configure log levels
    configure_log_levels()
    
    # Log initialization
    root_logger.info('Enhanced logging system initialized')
    root_logger.info(f'Log files directory: {os.path.abspath(log_dir)}')
    
    # Log environment info
    env_type = "Production" if os.environ.get("RENDER") == "true" else "Development"
    root_logger.info(f"Environment: {env_type}")
    root_logger.info(f"WebSocket mode: {'Enabled' if os.environ.get('REALTIME_ENABLED') == 'true' else 'Standard'}")
    
    return log_dir

# Context manager for capturing detailed timing information
class LoggingTimer:
    """Context manager for timing operations with detailed logging."""
    
    def __init__(self, logger, operation_name, log_level=logging.DEBUG, extra=None):
        self.logger = logger
        self.operation_name = operation_name
        self.log_level = log_level
        self.extra = extra or {}
        self.start_time = None
        self.operation_id = str(uuid.uuid4())[:8]
    
    def __enter__(self):
        self.start_time = time.time()
        self.logger.log(
            self.log_level, 
            f"START {self.operation_name} [ID:{self.operation_id}]",
            extra=self.extra
        )
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        end_time = time.time()
        duration = (end_time - self.start_time) * 1000  # Convert to milliseconds
        
        if exc_type:
            self.logger.error(
                f"ERROR {self.operation_name} [ID:{self.operation_id}] failed after {duration:.2f}ms: {exc_val}",
                extra=self.extra
            )
            if exc_tb:
                self.logger.error(
                    f"Traceback: {''.join(traceback.format_tb(exc_tb))}",
                    extra=self.extra
                )
        else:
            self.logger.log(
                self.log_level,
                f"END {self.operation_name} [ID:{self.operation_id}] completed in {duration:.2f}ms",
                extra=self.extra
            )

# Special detailed logger for WebSocket events
def log_websocket_event(event_type, data, call_sid=None, direction=None, extra_info=None):
    """Log a WebSocket event with detailed information."""
    extra = {
        'event_type': event_type,
        'timestamp': datetime.now().isoformat(),
        'call_sid': call_sid,
        'direction': direction or 'UNKNOWN'
    }
    
    if extra_info:
        extra.update(extra_info)
    
    # Create a clean version of data for logging
    log_data = data
    if isinstance(data, dict):
        # If it's a dict, make a copy to avoid modifying the original
        log_data = data.copy()
        
        # Handle sensitive or binary data
        if 'media' in log_data and 'payload' in log_data['media']:
            payload_size = len(log_data['media']['payload'])
            log_data['media']['payload'] = f"<{payload_size} bytes of binary data>"
        
        # Handle large text data
        if 'text' in log_data and isinstance(log_data['text'], str) and len(log_data['text']) > 1000:
            log_data['text'] = log_data['text'][:1000] + "... [truncated]"
    
    # Log with appropriate detail level based on event type
    if event_type in ['ping', 'pong', 'heartbeat']:
        ws_logger.debug(f"[{direction}] {event_type}", extra=extra)
    elif event_type == 'media':
        stream_logger.debug(
            f"[{direction}] Media chunk received/sent", 
            extra={**extra, 'media_size': len(data.get('media', {}).get('payload', ''))}
        )
    else:
        log_message = f"[{direction}] {event_type}"
        
        # For more interesting events, include the data
        if event_type in ['transcript', 'message', 'start', 'stop', 'error', 'tool_call']:
            try:
                log_message += f": {json.dumps(log_data)}"
            except (TypeError, json.JSONDecodeError):
                log_message += f": {str(log_data)}"
                
        ws_logger.info(log_message, extra=extra)
    
    # If this event is associated with a call, also log to the session log
    if call_sid:
        session_logger = get_session_logger(call_sid)
        session_logger.info(f"[WS:{direction}] {event_type}", extra=extra)

# Special logger for voice system state transitions
def log_voice_state_transition(old_state, new_state, call_sid, trigger=None, context=None):
    """Log a state transition in the voice system."""
    extra = {
        'call_sid': call_sid,
        'old_state': old_state,
        'new_state': new_state,
        'trigger': trigger,
        'timestamp': datetime.now().isoformat()
    }
    
    # Create a formatted message
    message = f"[STATE] {old_state} -> {new_state}"
    if trigger:
        message += f" (triggered by: {trigger})"
    
    # Log to the voice logger
    voice_logger.info(message, extra=extra)
    
    # Also log to the session logger
    session_logger = get_session_logger(call_sid)
    session_logger.info(message, extra=extra)
    
    # Log context if provided
    if context and isinstance(context, dict):
        context_msg = f"State transition context: {json.dumps(context)}"
        voice_logger.debug(context_msg, extra=extra)
        session_logger.debug(context_msg, extra=extra)

# Helper for logging OpenAI API calls
def log_openai_call(method, model, params=None, response=None, error=None, duration_ms=None, call_sid=None):
    """Log details of an OpenAI API call."""
    extra = {
        'method': method,
        'model': model,
        'call_sid': call_sid,
        'timestamp': datetime.now().isoformat()
    }
    
    # Create basic message
    message = f"[OPENAI] {method} to {model}"
    if duration_ms is not None:
        message += f" (took {duration_ms:.2f}ms)"
    
    # Log at different levels based on the outcome
    if error:
        openai_logger.error(f"{message} failed: {error}", extra=extra)
    else:
        openai_logger.info(message, extra=extra)
    
    # Log detailed parameters at debug level
    if params:
        # Clean params for logging (remove potential sensitive data)
        log_params = params.copy() if isinstance(params, dict) else params
        if isinstance(log_params, dict):
            if 'api_key' in log_params:
                log_params['api_key'] = '***'
        
        param_msg = f"Parameters: {json.dumps(log_params)}"
        openai_logger.debug(param_msg, extra=extra)
    
    # Log response summary at debug level
    if response:
        # For streaming responses, just note that it's a stream
        if hasattr(response, '__iter__') and not isinstance(response, (dict, list)):
            response_msg = "Response: <streaming response>"
        else:
            # For normal responses, include a summary
            response_summary = str(response)
            if len(response_summary) > 1000:
                response_summary = response_summary[:1000] + "... [truncated]"
            response_msg = f"Response: {response_summary}"
        
        openai_logger.debug(response_msg, extra=extra)
    
    # If associated with a call, also log to the session log
    if call_sid:
        session_logger = get_session_logger(call_sid)
        session_logger.info(message, extra=extra)

# Helper for logging agent interactions
def log_agent_interaction(agent_type, action, content, call_sid=None, duration_ms=None):
    """Log details of an agent interaction."""
    extra = {
        'agent_type': agent_type,
        'action': action,
        'call_sid': call_sid,
        'timestamp': datetime.now().isoformat()
    }
    
    # Create basic message
    message = f"[AGENT:{agent_type}] {action}"
    if duration_ms is not None:
        message += f" (took {duration_ms:.2f}ms)"
    
    # Log at info level
    agent_logger.info(message, extra=extra)
    
    # Log content at debug level
    if content:
        content_str = str(content)
        if len(content_str) > 1000:
            content_str = content_str[:1000] + "... [truncated]"
        
        content_msg = f"Content: {content_str}"
        agent_logger.debug(content_msg, extra=extra)
    
    # If associated with a call, also log to the session log
    if call_sid:
        session_logger = get_session_logger(call_sid)
        session_logger.info(message, extra=extra)

# Initialize logging when this module is imported
if __name__ != '__main__':
    initialize_logging()