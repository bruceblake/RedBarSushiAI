# System Optimizations for RedBarSushiAI

This document outlines the optimizations made to address memory issues and improve performance of the AI phone call system.

## Memory Optimizations

The application was experiencing memory issues that led to worker processes being terminated with SIGKILL (out of memory errors). The following changes have been made to address these issues:

1. **Reduced Worker Count**: Changed from 3 workers to 1 worker with 4 threads. This minimizes memory usage while maintaining throughput.

2. **Connection and Request Limits**: Reduced from 1000 to 500 for both connections and max requests to prevent memory bloat.

3. **Extended Menu Caching**: Increased menu cache duration from 5 minutes to 15 minutes to reduce database load and memory churn.

## X11 Display Dependency Removal

The system was experiencing errors related to X11 display connections. These changes fully eliminate X11 dependencies:

1. **Environment Variable Cleanup**: Removed all DISPLAY environment variables that were triggering X11 connection attempts.

2. **Headless Mode Enforcement**: Added specific environment variables to force all components into truly headless mode.

3. **X11 Error Detection**: Added specific handling for X11/display-related errors to gracefully switch to alternative implementations.

4. **Xvfb Removal**: Removed all Xvfb virtual display server attempts which were failing.

## OpenAI Realtime Audio Implementation

The system was experiencing issues with the OpenAI Realtime client not being properly initialized. The following changes improve the handling of this service:

1. **Fully Headless Audio Processor**: Prioritized the fully headless implementation that has no X11 dependencies.

2. **Improved Error Detection**: Added specific error detection for display-related errors during initialization.

3. **Fallback Mechanism**: Enhanced fallback mechanism with multiple layers:
   - HeadlessAudioProcessor (primary)
   - BasicAudioProcessor (secondary)
   - MinimalAudioProcessor (last resort)

4. **Removed Auto-Installation**: Removed runtime dependency installation attempts which can cause stability issues in production.

## Usage Instructions

No changes to usage are required. The system will continue to function as before but with improved stability and performance.

The system now prioritizes:
1. Reliability: Workers will not exceed memory limits
2. Stability: Process recycling prevents memory leaks from accumulating
3. Graceful degradation: When OpenAI Realtime client is unavailable, the system falls back to standard streaming

## Monitoring

You may notice in the logs:
- Fewer "Worker was sent SIGKILL" errors
- More stable memory usage patterns
- Either "Successfully imported Session from openai_realtime_client" indicating realtime mode is working, or "Using OpenAI client with streaming instead of realtime client" indicating fallback mode