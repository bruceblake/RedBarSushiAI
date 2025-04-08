# System Optimizations for RedBarSushiAI

This document outlines the optimizations made to address memory issues and improve performance of the AI phone call system.

## Memory Optimizations

The application was experiencing memory issues that led to worker processes being terminated with SIGKILL (out of memory errors). The following changes have been made to address these issues:

1. **Reduced Worker Count**: Changed from 3 workers to 1 worker with 4 threads. This minimizes memory usage while maintaining throughput.

2. **Memory Limits**: Added `--max-memory-per-child=256000` to limit each worker's memory usage and ensure regular process recycling.

3. **Connection and Request Limits**: Reduced from 1000 to 500 for both connections and max requests to prevent memory bloat.

4. **Extended Menu Caching**: Increased menu cache duration from 5 minutes to 15 minutes to reduce database load and memory churn.

## OpenAI Realtime Audio Implementation

The system was experiencing issues with the OpenAI Realtime client not being properly initialized. The following changes improve the handling of this service:

1. **Proper Session Import**: Added direct import of `Session` class from `openai_realtime_client.client` module.

2. **Fallback Mechanism**: Improved the fallback mechanism to use standard OpenAI streaming API when realtime is not available.

3. **Error Handling**: Enhanced error handling to gracefully degrade service without crashing.

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