# WebSocket Architecture for RedBarSushiAI Voice System

This document provides an in-depth overview of the WebSocket architecture used in the RedBarSushiAI voice ordering system, including connection flows, stability mechanisms, and troubleshooting procedures.

## Connection Flow Overview

The system uses a multi-phase WebSocket connection process to ensure reliability throughout the voice interaction:

1. **Initialization Phase**: Client establishes WebSocket connection
   - Connection parameters validated
   - Session created and stored in Redis
   - Initial handshake completed
   - Aggressive connection stabilization with rapid keep-alives

2. **Streaming Phase**: Audio data exchanged bidirectionally
   - Client sends audio in 20ms chunks
   - Server processes audio with OpenAI Realtime API
   - Response audio streamed back to client
   - Adaptive keep-alive frequency based on connection quality
   
3. **Termination Phase**: Graceful connection closure
   - Final messages processed
   - Session state archived
   - Connection resources released
   - Status summary logged for diagnostics

## Connection Stability Mechanisms

The system implements multiple layers of protection to maintain stable WebSocket connections, particularly during the critical post-greeting phase when disconnections are most likely to occur.

### Keep-Alive Strategy

The system uses an adaptive keep-alive approach that varies based on the connection state and quality:

1. **Initial Burst**: Extremely aggressive keep-alive messages during connection initialization
   - 200ms intervals during first few seconds
   - Creates a robust connection foundation

2. **Critical Phase Protection**: More frequent keep-alives during critical conversation states
   - Extra keep-alives sent immediately after greeting
   - Continuous connection validation during state transitions

3. **Adaptive Frequency**: Keep-alive interval adjusts based on connection quality
   - Higher frequency when connection quality decreases
   - Reduced frequency when connection is stable

4. **Recovery Pings**: Alternative ping formats if standard keep-alives fail
   - Multiple message formats to bypass potential filtering
   - Special emergency recovery messages during connection degradation

### Connection Quality Monitoring

The system continuously monitors connection health:

1. **Health Scoring**: Connection quality score (0-100) calculated based on:
   - Message throughput metrics
   - Response latency measurements
   - Error frequency analysis
   - State transition history

2. **Proactive Intervention**: Automatic actions when quality degrades
   - Increased keep-alive frequency
   - Alternative message formats
   - Recovery attempts before disconnection

3. **Comprehensive Logging**: Detailed event logging for diagnostics
   - Connection lifecycle events
   - State transitions
   - Error conditions with context
   - Performance metrics

### Error Recovery

The system implements robust error recovery mechanisms:

1. **Progressive Backoff**: Intelligent reconnection attempts
   - Exponential backoff with jitter
   - Automatic retry with increasing delays
   - Maximum retry limits with fallback options

2. **State Preservation**: Session state maintained across reconnections
   - Conversation context preserved in Redis
   - Streaming state backed up regularly
   - Seamless recovery when possible

3. **Graceful Degradation**: Progressive functionality reduction
   - Falls back to less real-time operations if needed
   - Maintains core functionality during instability
   - Prioritizes critical conversational functionality

## Voice Activity Detection (VAD)

The system includes context-aware Voice Activity Detection (VAD) with settings optimized for different conversation phases:

1. **Greeting Phase**: Quick response to initial silence
   - Shorter timeout (1.5s)
   - Lower speech detection threshold
   - Optimized for initial engagement

2. **Ordering Phase**: Patient listening during complex responses
   - Longer timeout (3.0s)
   - Higher tolerance for pauses
   - Designed for complex menu selections

3. **Confirmation Phase**: Tuned for yes/no responses
   - Quick timeout for simple responses (1.2s)
   - Optimized for conversation flow
   - Balanced to prevent false silence detection

4. **Dynamic Adjustment**: VAD settings adapt as conversation progresses
   - Automatically adjusts based on FSM state
   - Fine-tuned for optimal user experience
   - Prevents premature interruptions

## WebSocket Implementation Classes

The WebSocket implementation consists of several key components:

### Connection Manager

The `ConnectionManager` class is responsible for tracking connection state and health:

```python
class ConnectionManager:
    """Manages WebSocket connections with advanced stability features."""
    
    def __init__(self, session_id):
        self.session_id = session_id
        self.state = ConnectionState.INITIALIZING
        # Additional properties and metrics...
    
    def update_state(self, new_state, reason=None):
        """Update the connection state with logging."""
        
    def assess_connection_health(self):
        """Calculate health score and identify issues."""
        
    def get_status_report(self):
        """Generate comprehensive status report."""
```

### Stream Handler

The `robust_stream_handler` module manages the WebSocket connection lifecycle:

```python
async def handle_robust_media_stream(ws, session_id=None):
    """Enhanced WebSocket handler with robust connection management."""
    # Initialize connection manager
    conn_mgr = ConnectionManager(session_id)
    
    # Start maintenance tasks
    maintenance_task = asyncio.create_task(maintain_connection(ws, conn_mgr))
    monitor_task = asyncio.create_task(monitor_connection_health(ws, conn_mgr))
    
    # Process the media stream with error handling and recovery
    # ...
```

### Connection Maintenance

The system uses dedicated tasks for connection maintenance:

```python
async def maintain_connection(ws, connection_manager):
    """Maintain WebSocket connection with adaptive keep-alive messages."""
    # Initial burst of keep-alives
    # ...
    
    # Main keep-alive loop with adaptive intervals
    while True:
        # Get adaptive interval based on connection state
        interval = await get_adaptive_ping_interval(connection_manager)
        # Send keep-alive message
        # ...
```

## Timeouts and Intervals

The system uses carefully tuned timeouts and intervals to ensure optimal stability:

| Connection Phase | Keep-Alive Interval | Purpose |
|------------------|---------------------|---------|
| Initialization   | 200ms               | Establish robust connection |
| Post-greeting    | 300ms               | Protect critical phase |
| Stable operation | 3000ms              | Maintain established connection |
| Degraded state   | 1000ms              | Recover from instability |

| VAD Context      | Silence Timeout     | Purpose |
|------------------|---------------------|---------|
| Greeting         | 1.5s                | Quick initial response |
| Ordering         | 3.0s                | Patient during ordering |
| Confirmation     | 1.2s                | Prompt for yes/no answers |
| Complex ordering | 4.0s                | Maximum patience for complexity |

## Testing and Validation

The WebSocket system includes comprehensive testing:

1. **Unit Tests**: Verify component functionality
   - Connection manager tests
   - Protocol handling tests
   - Error recovery tests

2. **Integration Tests**: Verify component interactions
   - Full connection lifecycle tests
   - State transition tests
   - Audio processing integration tests

3. **Resilience Tests**: Verify stability under duress
   - Connection failure simulation tests
   - Network degradation tests
   - Recovery capability tests

4. **Load Tests**: Verify performance under load
   - Concurrent connection tests
   - Long-running stability tests
   - Resource utilization tests

## Troubleshooting Guide

### Common Issues and Solutions

1. **Frequent Disconnections**
   - **Symptoms**: WebSocket connections close unexpectedly during calls
   - **Diagnosis**: Check connection health logs for specific error patterns
   - **Solutions**:
     - Verify keep-alive configuration (see `app/routes/voice/utils/connection_manager.py`)
     - Check for network stability issues in the deployment environment
     - Ensure timeout settings match expected network latency

2. **Audio Processing Delays**
   - **Symptoms**: Delayed responses, gaps in conversation
   - **Diagnosis**: Check streaming logs for audio chunk processing metrics
   - **Solutions**:
     - Verify OpenAI Realtime API connection stability
     - Check buffer sizing and audio chunk processing
     - Adjust VAD settings for conversation context

3. **Greeting Failures**
   - **Symptoms**: System fails to send greeting or disconnects post-greeting
   - **Diagnosis**: Examine connection timing logs around greeting event
   - **Solutions**:
     - Verify post-greeting stability mechanism is active
     - Check FSM state transition from GREETING to MAIN_MENU
     - Verify keep-alive rate increases after greeting

### Diagnostic Tools

1. **Connection Health Check**
   - Access `/voice/debug/ws_health` endpoint
   - Check active connection count and quality scores
   - Review connection health distribution

2. **Session Inspection**
   - View detailed session logs in `logs/media_stream_{session_id}.log`
   - Analyze connection lifecycle events
   - Identify exact failure points

3. **Realtime Monitoring**
   - Use WebSocket monitoring dashboard
   - Track active connections and health metrics
   - Set alerts for quality score thresholds

### Recovery Procedures

1. **Immediate Response**
   - Identify affected connections from logs
   - Check for common patterns (carrier, region, timing)
   - Verify Redis and database connectivity

2. **Service Restoration**
   - Increase keep-alive frequency if needed
   - Adjust VAD settings for problematic phases
   - Implement emergency stability fixes if needed

3. **Long-term Resolution**
   - Analyze aggregated connection data
   - Identify systemic causes of instability
   - Update config parameters in deployment

## Configuration Parameters

The WebSocket system can be tuned with environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `WS_KEEPALIVE_ENABLED` | `true` | Enable/disable keep-alive mechanism |
| `WS_INITIAL_KEEPALIVE_INTERVAL` | `0.2` | Initial burst interval (seconds) |
| `WS_STABLE_KEEPALIVE_INTERVAL` | `3.0` | Stable operation interval (seconds) |
| `WS_CONNECTION_TIMEOUT` | `30` | Connection inactivity timeout (seconds) |
| `WS_MAX_RECOVERY_ATTEMPTS` | `5` | Maximum recovery attempts before giving up |
| `WS_VAD_GREETING_TIMEOUT` | `1.5` | Silence timeout for greeting phase (seconds) |

## Deployment Considerations

### Render Deployment

For deployment on Render, ensure these settings:

1. **WebSocket Configuration**
   - In `render.yaml`, set appropriate WebSocket timeout
   - Configure headers for WebSocket upgrade
   - Set secure WebSocket protocol (wss://)

2. **Worker Configuration**
   - Use `geventwebsocket.gunicorn.workers.GeventWebSocketWorker`
   - Configure appropriate worker count based on load
   - Set proper keepalive settings

Example Procfile configuration:
```
web: gunicorn -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker -w 2 --timeout 120 'run:app'
```

### Twilio Media Streams Configuration

1. **Proper TwiML Configuration**
   - Use `<Connect><Stream>` for bidirectional streaming
   - Ensure WebSocket URL is correctly formatted
   - Set appropriate track parameters

Example TwiML:
```xml
<Response>
    <Connect>
        <Stream url="wss://redbarsushi-staging.onrender.com/ws/voice/media" track="both_tracks" />
    </Connect>
</Response>
```

2. **Twilio Account Settings**
   - Enable Media Streams feature flag
   - Ensure proper SID and token configuration
   - Set appropriate webhook URLs