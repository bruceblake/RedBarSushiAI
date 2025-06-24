# Performance Analysis Tools

This directory contains scripts for analyzing and monitoring the performance of RedBarSushiAI.

## Scripts

### analyze_redis_sessions.py

Analyzes Redis session storage patterns to identify optimization opportunities.

**Features:**
- Redis memory usage statistics
- FSM session size analysis
- Conversation store analysis
- Large key detection
- Performance recommendations

**Usage:**
```bash
python tools/performance_analysis/analyze_redis_sessions.py
```

### generate_test_sessions.py

Generates test FSM sessions and conversation data for performance testing.

**Features:**
- Creates realistic test sessions with varying sizes
- Simulates different conversation states
- Generates cart data and conversation history
- Useful for load testing

**Usage:**
```bash
python tools/performance_analysis/generate_test_sessions.py
```

## When to Use

Run these scripts when:
- Monitoring production Redis memory usage
- Planning for scale and capacity
- Investigating performance issues
- Evaluating need for Redis session optimization

## Future Enhancements

Based on the analysis results, consider:
1. Implementing session data compression
2. Using Redis Hash data types for better memory efficiency
3. Partitioning large session data
4. Setting up automated monitoring alerts