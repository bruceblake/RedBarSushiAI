# System Optimizations for RedBarSushiAI

This document outlines the optimizations made to address memory issues and improve performance of the AI phone call system.

## User Experience Improvements

### Intelligent Name Extraction
- Added AI-based name extraction in voice calls
- Now intelligently detects names from phrases like "My name is John" or "This is Mary Smith"
- Handles common speech patterns and filler words
- Properly capitalizes names for consistent display

### Enhanced Order Clarifications

#### Better Handling of Unavailable Items
- Added clear messaging when items are unavailable
- Clearly marks items as "(not on menu)" or "(unavailable)" in order descriptions
- Separately lists unavailable items with specific reasons
- Calculates bill amount only using available items
- Provides helpful guidance instead of abruptly ending the call

#### Improved Order Quantity Display
- Enhanced order descriptions to consistently use "×" symbol for quantities
- More clearly shows multiple quantities of the same item
- Formats quantities consistently across all parts of the system

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

The system was experiencing issues with the OpenAI Realtime client not being properly initialized due to X11 dependencies. The following changes provide a complete solution:

1. **Direct WebSocket Implementation**: Added a completely custom implementation that uses WebSockets to connect directly to the OpenAI Realtime API without any X11 dependency.

2. **Prioritized Implementation Order**:
   - DirectRealtimeAudioProcessor (primary) - uses custom WebSocket implementation
   - HeadlessAudioProcessor (secondary) - simplified implementation with no X11 dependency
   - BasicAudioProcessor (tertiary) - standard API with streaming
   - MinimalAudioProcessor (last resort) - minimal implementation for emergencies

3. **Improved Error Detection**: Added specific handling for X11/display-related errors to gracefully switch to alternative implementations.

4. **Testing Script**: Added test_realtime_client.py that helps diagnose issues with each implementation.

5. **Removed Auto-Installation**: Removed runtime dependency installation attempts which can cause stability issues in production.

## Enhanced Speech Recognition for Menu Items

The system now includes specialized speech recognition improvements for restaurant menu items, making it more reliable for taking food orders:

1. **Menu-Aware Whisper Prompting**: The system now uses menu item names as Whisper prompts, which dramatically improves recognition of menu items in customer speech.

2. **Post-Processing with GPT-4o**: Customer transcripts are post-processed with GPT to correct menu item names and improve recognition quality.

3. **Automatic Menu Parsing**: The system dynamically extracts menu items from your menu data file to use in the speech recognition chain.

4. **Twilio Audio Format Support**: Added specific support for Twilio's mulaw audio format at 8kHz sampling rate.

5. **Restaurant-Optimized Voice Prompts**: Added specialized system prompts for the restaurant context to improve the natural flow of phone conversations.

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