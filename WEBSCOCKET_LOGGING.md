# Enhanced WebSocket Logging System

This document explains the enhanced WebSocket logging system implemented for the RedBarSushi AI voice system.

## Overview

The enhanced logging system provides detailed logging and monitoring for WebSocket connections, particularly focused on Twilio Media Streams integration with OpenAI's Realtime API. It helps with diagnosing connection issues, tracking message flow, and monitoring system performance.

## Components

### 1. Enhanced Logging Base (`app/utils/enhanced_logging.py`)

- Configures specialized loggers for different system components
- Provides hierarchical logging with directory-based organization
- Implements session-specific logging
- Includes timing utilities and context managers

### 2. WebSocket-specific Logging (`app/routes/voice/utils/websocket_logging.py`)

- Specialized logging for WebSocket connections
- Decorators for WebSocket handler functions
- Message flow tracking and formatting
- Statistics collection for connections

### 3. Integration in Voice System (`app/routes/voice/realtime/stream_handler.py`)

- Uses enhanced logging in WebSocket media stream handler
- Tracks connection statistics and timings
- Provides detailed diagnostic information for debugging

### 4. Monitoring Endpoints (`app/routes/monitoring.py`)

- `/monitoring/websocket/stats` - View current WebSocket connection statistics
- Enhanced `/monitoring/health` endpoint with WebSocket component status

## Key Features

### Connection Lifecycle Tracking

Detailed logging throughout the WebSocket connection lifecycle:
- Connection establishment
- Message exchange
- Error handling
- Graceful disconnection

### Message Flow Analysis

- Tracks both incoming and outgoing messages
- Formats complex messages for easier debugging
- Tracks message size and type information

### Statistics Collection

Collects key metrics about WebSocket usage:
- Active connections
- Total connections
- Message counts and sizes
- Connection durations
- Error rates

### Session-based Logging

- Creates dedicated log files for each session
- Correlates logs across system components
- Makes it easier to debug specific user sessions

## Usage

### Viewing WebSocket Statistics

Check current WebSocket statistics:
```bash
curl https://redbarsushi-staging.onrender.com/monitoring/websocket/stats
```

### Checking WebSocket System Health

View WebSocket system health status:
```bash
curl https://redbarsushi-staging.onrender.com/monitoring/health
```

### Debugging Connections

1. Check the session-specific logs in the `logs/sessions/` directory
2. Use the WebSocket stats endpoint to get current connection counts
3. Enable debug logging by setting the environment variable:
   ```
   LOG_LEVEL_WEBSOCKET=DEBUG
   ```

## Configuration for Deployment

The system includes configuration for deployment environments:

1. **Docker Support**: PortAudio system dependencies included in the Dockerfile
2. **Render Deployment**: Updated render.yaml with proper system dependency installation
3. **Fallback Mechanisms**: For environments where audio libraries aren't available

## Implementation Details

### Decorator Pattern

The `@websocket_handler` decorator wraps WebSocket handlers with:
- Connection tracking
- Error handling
- Message logging
- Statistics collection

### WebSocket Method Wrapping

Wraps WebSocket's `send` and `receive` methods to:
- Log all messages in a consistent way
- Count message statistics
- Format binary data
- Catch and record errors

### Error Recovery

Includes mechanisms to gracefully handle errors:
- Logs detailed error information
- Sends error messages to clients
- Updates statistics for monitoring
- Ensures connections are properly closed