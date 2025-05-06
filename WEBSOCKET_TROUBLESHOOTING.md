# WebSocket Troubleshooting Guide for RedBarSushiAI

This document provides detailed guidance for diagnosing and resolving WebSocket connection issues in the RedBarSushiAI voice ordering system.

## Common Connection Issues

### 1. Immediate Disconnections

**Symptoms:**
- WebSocket connections close within seconds of establishment
- Error logs show `connection_closed` events shortly after `connection_established`
- No audio data processing occurs

**Potential Causes:**
- WebSocket handshake failures
- Missing WebSocket protocol headers
- Invalid WebSocket protocol version negotiation
- Firewall or proxy blocking WebSocket connections

**Diagnostic Steps:**
1. Check server logs for handshake errors:
   ```bash
   grep "handshake" logs/websocket_connections.log | tail -n 50
   ```

2. Verify TwiML configuration:
   ```bash
   curl -s https://your-server.com/voice | grep -o "<Stream.*>"
   ```

3. Examine WebSocket upgrade headers in HAR capture or logs

**Resolution:**
1. Update TwiML to include proper WebSocket protocol:
   ```xml
   <Stream url="wss://your-server.com/ws/voice/media" track="both_tracks" />
   ```

2. Configure proper headers for WebSocket upgrade:
   ```
   Connection: Upgrade
   Upgrade: websocket
   Sec-WebSocket-Version: 13
   Sec-WebSocket-Protocol: twilio-media-stream
   ```

3. Ensure firewall allows WebSocket connections:
   ```bash
   # Check if port 443 is open for WSS connections
   curl -v -N wss://your-server.com/ws/voice/media
   ```

### 2. Post-Greeting Disconnections

**Symptoms:**
- Connections work initially and greeting is sent successfully
- Disconnection occurs shortly after greeting (within 1-5 seconds)
- Logs show `greeting_sent` followed quickly by `connection_closed`

**Potential Causes:**
- Insufficient keep-alive frequency after greeting
- Client-side timeout configuration too aggressive
- Network conditions causing packet loss during critical phase
- VAD configuration causing silent periods that lead to timeouts

**Diagnostic Steps:**
1. Check connection health around greeting time:
   ```bash
   grep -A 20 "GREETING" logs/media_stream_*.log
   ```

2. Examine keep-alive frequency and response:
   ```bash
   grep "keep_alive" logs/media_stream_*.log | wc -l
   ```

3. Check for silence events immediately after greeting:
   ```bash
   grep -A 10 "silence_detected" logs/media_stream_*.log
   ```

**Resolution:**
1. Increase keep-alive frequency specifically for post-greeting phase:
   ```python
   # In app/routes/voice/utils/connection_manager.py
   if connection_manager.state == ConnectionState.GREETING:
       return 0.3  # Very aggressive 300ms interval
   ```

2. Add additional post-greeting stabilization messages:
   ```python
   # Send multiple stabilization messages after greeting
   for i in range(5):
       stabilize_msg = {...}  # Create message
       await ws.send(json.dumps(stabilize_msg))
       await asyncio.sleep(0.1)  # Very short delay
   ```

3. Adjust VAD settings for greeting phase:
   ```python
   # In app/routes/voice/utils/vad.py
   if context == "greeting":
       base_config.update({
           "timeout": 2.0,  # Increased from 1.5s
           "speech_started_delay": 0.2,
       })
   ```

### 3. Audio Processing Failures

**Symptoms:**
- WebSocket connection remains open but no audio is processed
- Logs show incoming audio chunks but no transcripts or events
- System appears "stuck" with customer unable to interact

**Potential Causes:**
- Incorrect audio format or encoding
- Buffer overflow in audio processing pipeline
- OpenAI Realtime API connection issues
- Threading/async issues preventing audio processing

**Diagnostic Steps:**
1. Check audio format from client:
   ```bash
   grep "mediaFormat" logs/media_stream_*.log
   ```

2. Verify audio chunks are being received and processed:
   ```bash
   grep "audio_chunks" logs/media_stream_*.log | tail -n 20
   ```

3. Examine OpenAI Realtime API connection status:
   ```bash
   grep "OpenAI Realtime" logs/media_stream_*.log
   ```

**Resolution:**
1. Ensure proper audio format configuration:
   ```python
   # Verify format conversion is correct
   if media_format["encoding"] == "audio/x-mulaw":
       # Convert μ-law to PCM16 correctly
       audio_chunk = convert_mulaw_to_pcm16(audio_chunk)
   ```

2. Implement buffer management to prevent overflow:
   ```python
   # Limit queue size and implement overflow handling
   if incoming_audio_queue.qsize() > MAX_QUEUE_SIZE:
       # Clear oldest chunks to prevent processing delay
       logger.warning(f"Audio queue overflow, clearing oldest chunks")
       while incoming_audio_queue.qsize() > MAX_QUEUE_SIZE / 2:
           await incoming_audio_queue.get()
   ```

3. Add error recovery for OpenAI Realtime API:
   ```python
   # Implement fallback processing for API issues
   try:
       transcript = await realtime_processor.process_audio_chunk(audio_chunk)
   except Exception as e:
       logger.error(f"Realtime API error: {e}")
       # Fall back to batch processing
       transcript = await fallback_processor.process_audio(audio_chunk)
   ```

## Silent Failure Cases

### 1. "Ghost" Connections

**Symptoms:**
- WebSocket connections appear active but no messages are flowing
- Logs show active connection but no events for extended periods
- Resources consumed but no useful work being done

**Diagnostic Steps:**
1. Identify potential ghost connections:
   ```bash
   grep "last_activity" logs/websocket_*.log | grep -E "time_since_activity.*[3-9][0-9]"
   ```

2. Check connection state from status reports:
   ```bash
   grep "WebSocket Status Report" logs/media_stream_*.log | tail -n 50
   ```

**Resolution:**
1. Implement aggressive timeout detection:
   ```python
   # In app/routes/voice/utils/connection_manager.py
   if time.time() - conn_mgr.last_activity_time > 20:
       conn_mgr.log_health_event("WARNING", f"No activity for 20+ seconds, connection may be stale")
       # Force activity or close connection
       await ws.send(json.dumps({"type": "ping", "timestamp": time.time()}))
   ```

2. Add periodic health checks that will close dead connections:
   ```python
   # Schedule periodic health checks
   def periodic_health_check():
       for session_id, conn in active_connections.items():
           if time.time() - conn.last_activity_time > 30:
               logger.warning(f"Connection {session_id} inactive for 30+ seconds, closing")
               # Force close the connection
               asyncio.create_task(force_close_connection(session_id))
   ```

### 2. Memory Leaks

**Symptoms:**
- Increasing memory usage over time despite constant connection count
- Slow performance degradation after extended uptime
- Eventual OOM errors or container restarts

**Diagnostic Steps:**
1. Track active connection count over time:
   ```bash
   grep "active connections" logs/websocket_*.log | tail -n 100
   ```

2. Check for tasks that aren't being cleaned up:
   ```bash
   grep "registered" logs/websocket_*.log | wc -l
   grep "completed" logs/websocket_*.log | wc -l
   # These counts should be similar over time
   ```

**Resolution:**
1. Ensure proper task cleanup in all cases:
   ```python
   # Always clean up tasks in finally block
   finally:
       try:
           # Cancel all tasks associated with this connection
           for task in conn_mgr.tasks:
               if not task.done():
                   task.cancel()
           
           # Remove from active connections registry
           if session_id in active_connections:
               del active_connections[session_id]
       except Exception as e:
           logger.error(f"Cleanup error: {e}")
   ```

2. Implement periodic orphan task detection:
   ```python
   # Periodically check for orphaned tasks
   def check_for_orphan_tasks():
       """Find tasks that exist but aren't linked to active connections."""
       active_session_ids = set(active_connections.keys())
       task_session_ids = set()
       
       for task in asyncio._connection_tasks:
           # Extract session ID from task name or context
           if hasattr(task, 'session_id'):
               task_session_ids.add(task.session_id)
       
       # Find orphans
       orphans = task_session_ids - active_session_ids
       if orphans:
           logger.warning(f"Found {len(orphans)} orphaned tasks: {orphans}")
           # Cancel orphaned tasks
           for task in list(asyncio._connection_tasks):
               if hasattr(task, 'session_id') and task.session_id in orphans:
                   logger.info(f"Cancelling orphaned task for session {task.session_id}")
                   task.cancel()
   ```

## Environment-Specific Issues

### 1. Render-Specific WebSocket Issues

**Symptoms:**
- WebSocket connections work in development but fail on Render
- Connections timeout after specific duration (typically 55-60 seconds)
- Logs show consistent disconnection patterns

**Diagnostic Steps:**
1. Check Render-specific logs:
   ```bash
   grep "render" logs/websocket_*.log
   ```

2. Verify proper Render WebSocket configuration:
   ```bash
   grep -i "websocket" render.yaml
   ```

**Resolution:**
1. Update Render configuration for WebSocket support:
   ```yaml
   # In render.yaml
   services:
     - type: web
       plan: standard
       name: redbarsushi
       env: python
       buildCommand: ./render_build.sh
       startCommand: gunicorn -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker -w 2 --timeout 120 'run:app'
       envVars:
         - key: WS_KEEPALIVE_ENABLED
           value: "true"
   ```

2. Set proper headers in Render environment:
   ```python
   # In app/routes/__init__.py
   @app.after_request
   def add_header(response):
       # Ensure WebSocket connections work on Render
       if request.environ.get('HTTP_UPGRADE', '').lower() == 'websocket':
           # Allow WebSocket upgrade
           response.headers['Connection'] = 'Upgrade'
       return response
   ```

### 2. Twilio Media Streams Integration Issues

**Symptoms:**
- Twilio initiates connection but fails to send audio
- Logs show connection established but no media events
- Console errors in Twilio logs

**Diagnostic Steps:**
1. Check Twilio logs for WebSocket errors:
   ```
   # In Twilio Console, navigate to:
   # Monitor > Logs > Programmable Voice Logs
   # Filter for the specific call SID
   ```

2. Verify proper TwiML configuration:
   ```bash
   curl -s https://your-server.com/voice | grep -A 10 "<Stream"
   ```

**Resolution:**
1. Update TwiML for proper Media Streams integration:
   ```xml
   <Response>
     <Connect>
       <Stream url="wss://your-server.com/ws/voice/media" track="both_tracks" />
     </Connect>
   </Response>
   ```

2. Ensure proper WebSocket protocol negotiation:
   ```python
   # In your WebSocket handler, ensure you accept the correct subprotocol
   @app.websocket('/ws/voice/media')
   async def handle_media_stream(websocket):
       # Verify and accept the correct subprotocol
       if 'twilio-media-stream' in websocket.requested_subprotocols:
           await websocket.accept('twilio-media-stream')
       else:
           await websocket.accept()
   ```

## Monitoring and Alerting

### Setting Up Connection Quality Monitoring

1. **Create a WebSocket Health Dashboard**

   Implement a simple health dashboard endpoint:
   ```python
   @app.route('/ws/health')
   def websocket_health():
       """Return WebSocket connection health statistics."""
       stats = {
           "active_connections": len(active_connections),
           "connection_quality": {
               "excellent": 0,
               "good": 0,
               "fair": 0,
               "poor": 0,
               "critical": 0
           },
           "recent_errors": []
       }
       
       # Count connections by quality
       for session_id, conn in active_connections.items():
           quality = conn.connection_quality
           if quality >= 90:
               stats["connection_quality"]["excellent"] += 1
           elif quality >= 70:
               stats["connection_quality"]["good"] += 1
           elif quality >= 50:
               stats["connection_quality"]["fair"] += 1
           elif quality >= 30:
               stats["connection_quality"]["poor"] += 1
           else:
               stats["connection_quality"]["critical"] += 1
       
       # Get recent errors
       error_log = read_recent_errors(limit=10)
       stats["recent_errors"] = error_log
       
       return jsonify(stats)
   ```

2. **Implement Alert Conditions**

   Set up alerts for critical WebSocket conditions:
   ```python
   def check_alert_conditions():
       """Check for alert conditions in WebSocket connections."""
       alert_conditions = []
       
       # Check for critical connection quality
       critical_connections = [
           conn for conn in active_connections.values()
           if conn.connection_quality < 30
       ]
       if len(critical_connections) > 3:
           alert_conditions.append({
               "level": "critical",
               "message": f"{len(critical_connections)} connections in critical state",
               "timestamp": time.time()
           })
       
       # Check for high error rate
       recent_errors = len([
           event for conn in active_connections.values()
           for event in conn.health_log
           if event["type"] == "ERROR" and time.time() - event["timestamp"] < 300
       ])
       if recent_errors > 10:
           alert_conditions.append({
               "level": "warning",
               "message": f"High error rate: {recent_errors} errors in last 5 minutes",
               "timestamp": time.time()
           })
       
       # Send alerts
       if alert_conditions:
           send_alerts(alert_conditions)
   ```

### Log Analysis Patterns

Use these log analysis patterns to identify common issues:

1. **Find Frequent Disconnections**
   ```bash
   grep "DISCONNECT" logs/websocket_*.log | awk '{print $4}' | sort | uniq -c | sort -nr
   ```

2. **Identify Poor Connection Quality**
   ```bash
   grep "connection health" logs/media_stream_*.log | grep -E "health.*[0-4][0-9]" | tail -n 20
   ```

3. **Find Connections Stuck in Specific States**
   ```bash
   grep "STATE" logs/websocket_*.log | grep -v "CLOSED\|STABLE" | tail -n 50
   ```

4. **Analyze Keep-Alive Effectiveness**
   ```bash
   # Count keep-alives by session ID
   grep "keep_alive" logs/websocket_*.log | awk '{print $4}' | sort | uniq -c | sort -nr
   ```

5. **Track Greeting Success Rate**
   ```bash
   # Count total sessions
   total=$(grep "NEW WEBSOCKET CONNECTION" logs/websocket_connections.log | wc -l)
   # Count sessions with greeting
   greeted=$(grep "GREETING" logs/websocket_*.log | awk '{print $4}' | sort | uniq | wc -l)
   # Calculate percentage
   echo "Greeting success rate: $((greeted * 100 / total))%"
   ```

## Recovery Playbook

### 1. Emergency Response for Connection Instability

If you observe widespread connection failures, follow these steps:

1. **Immediate Triage**
   ```bash
   # Check active connections
   curl -s https://your-server.com/ws/health | jq
   
   # Identify failure patterns
   grep -i "error\|failed\|closed" logs/websocket_*.log | tail -n 50
   ```

2. **Implement Emergency Stability Measures**
   
   Update environment variables to increase stability:
   ```bash
   # Increase keep-alive frequency
   export WS_STABLE_KEEPALIVE_INTERVAL=1.0
   
   # Increase connection timeout
   export WS_CONNECTION_TIMEOUT=60
   
   # Apply changes with minimal downtime
   supervisorctl restart web
   ```

3. **Monitor Recovery**
   ```bash
   # Watch for improved connection stability
   watch -n 5 'curl -s https://your-server.com/ws/health | jq'
   
   # Monitor error rate
   watch -n 5 'grep -i "error" logs/websocket_*.log | wc -l'
   ```

### 2. Scheduled Maintenance Procedure

For planned updates to WebSocket infrastructure, follow this procedure:

1. **Pre-Maintenance Checks**
   ```bash
   # Verify current performance
   curl -s https://your-server.com/ws/health | jq
   
   # Check for existing issues
   grep -i "error" logs/websocket_*.log | wc -l
   ```

2. **Graceful Connection Termination**
   ```python
   # Implement in your maintenance script
   async def graceful_shutdown():
       """Gracefully shut down all WebSocket connections."""
       logger.info(f"Starting graceful shutdown of {len(active_connections)} connections")
       
       # Send goodbye message to all connections
       for session_id, conn in active_connections.items():
           try:
               # Get WebSocket for this connection
               ws = conn.websocket
               
               # Send goodbye message
               goodbye = {
                   "type": "maintenance",
                   "message": "Server maintenance in progress, please reconnect in 5 minutes",
                   "timestamp": time.time()
               }
               await ws.send(json.dumps(goodbye))
               
               # Wait briefly to ensure message is sent
               await asyncio.sleep(0.1)
               
               # Close connection gracefully
               await ws.close(1001, "Maintenance")
               
               logger.info(f"Gracefully closed connection {session_id}")
           except Exception as e:
               logger.error(f"Error during graceful close of {session_id}: {e}")
       
       # Wait for connections to fully close
       await asyncio.sleep(5)
       
       # Verify all connections are closed
       remaining = len(active_connections)
       if remaining > 0:
           logger.warning(f"{remaining} connections still active after graceful shutdown")
   ```

3. **Post-Maintenance Verification**
   ```bash
   # Verify service is accepting new connections
   curl -v -N -H "Connection: Upgrade" -H "Upgrade: websocket" \
        -H "Sec-WebSocket-Version: 13" -H "Sec-WebSocket-Key: SGVsbG8sIHdvcmxkIQ==" \
        https://your-server.com/ws/voice/media
   
   # Monitor new connections after maintenance
   watch -n 5 'grep "NEW WEBSOCKET CONNECTION" logs/websocket_connections.log | wc -l'
   ```

## WebSocket Configuration Reference

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WS_KEEPALIVE_ENABLED` | `true` | Enable/disable keep-alive mechanism |
| `WS_INITIAL_KEEPALIVE_INTERVAL` | `0.2` | Initial burst interval (seconds) |
| `WS_STABLE_KEEPALIVE_INTERVAL` | `3.0` | Stable operation interval (seconds) |
| `WS_CONNECTION_TIMEOUT` | `30` | Connection inactivity timeout (seconds) |
| `WS_MAX_RECOVERY_ATTEMPTS` | `5` | Maximum recovery attempts before giving up |
| `WS_HEALTH_CHECK_INTERVAL` | `10` | Health monitoring interval (seconds) |
| `WS_LOG_LEVEL` | `INFO` | Logging level for WebSocket events |

### Health Score Interpretation

Understanding connection health scores:

| Score Range | Quality | Description |
|-------------|---------|-------------|
| 90-100 | Excellent | Perfect connection with no issues |
| 70-89 | Good | Stable connection with minimal issues |
| 50-69 | Fair | Functional connection with occasional issues |
| 30-49 | Poor | Problematic connection with frequent issues |
| 0-29 | Critical | Severely degraded connection requiring intervention |

Health scores are calculated based on:
- Message exchange success rate
- Latency and timing metrics
- Error frequency and severity
- Connection state stability

### Performance Benchmarks

Expected performance metrics for different deployment environments:

| Metric | Development | Staging | Production |
|--------|-------------|---------|------------|
| Connection Establishment | < 100ms | < 200ms | < 300ms |
| Keep-Alive Round Trip | < 50ms | < 100ms | < 150ms |
| Audio Chunk Processing | < 20ms | < 30ms | < 50ms |
| Time to First Transcript | < 1s | < 2s | < 3s |
| Maximum Concurrent Calls | 5 | 25 | 100 |

Monitor your deployment against these benchmarks to identify potential performance regressions.

## Additional Resources

- [WebSocket Protocol Specification (RFC 6455)](https://tools.ietf.org/html/rfc6455)
- [Twilio Media Streams API Documentation](https://www.twilio.com/docs/voice/media-streams)
- [OpenAI Realtime API Documentation](https://platform.openai.com/docs/api-reference/audio)
- [WEBSOCKET_ARCHITECTURE.md](WEBSOCKET_ARCHITECTURE.md) - Detailed architecture overview
- [SILENCE_HANDLING.md](SILENCE_HANDLING.md) - VAD and silence management details