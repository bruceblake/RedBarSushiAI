"""
System helper functions for the MCP server.

This module provides utility functions for system operations
used by the RedBarSushi MCP server tools.
"""

import os
import sys
import time
import json
import psutil
import threading
import traceback
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

def get_container_stats(interval: int = 1) -> Dict[str, Any]:
    """
    Get system statistics for the container.
    
    Args:
        interval: Time interval in seconds to measure CPU usage
        
    Returns:
        Dictionary with container statistics
    """
    try:
        # Get process info
        process = psutil.Process()
        
        # Get CPU usage (requires an interval)
        cpu_percent = process.cpu_percent(interval=interval)
        
        # Get memory info
        memory_info = process.memory_info()
        
        # Get disk usage
        disk_usage = psutil.disk_usage('/')
        
        # Get uptime
        uptime = time.time() - process.create_time()
        
        # Get thread count
        thread_count = process.num_threads()
        
        return {
            "cpu_percent": cpu_percent,
            "memory_usage_mb": memory_info.rss / (1024 * 1024),
            "memory_percent": process.memory_percent(),
            "disk_usage_percent": disk_usage.percent,
            "uptime_seconds": uptime,
            "thread_count": thread_count,
            "process_id": process.pid,
            "python_version": sys.version
        }
    except Exception as e:
        return {"error": str(e)}

def get_thread_dump() -> Dict[str, Any]:
    """
    Get a dump of all threads in the process.
    
    Returns:
        Dictionary with thread information
    """
    try:
        # Get all threads
        threads = threading.enumerate()
        
        # Get traceback for each thread
        thread_info = []
        for thread in threads:
            # Skip the current thread
            if thread.ident == threading.current_thread().ident:
                continue
            
            frame = sys._current_frames().get(thread.ident)
            if frame:
                stack = ''.join(traceback.format_stack(frame))
                thread_info.append({
                    "id": thread.ident,
                    "name": thread.name,
                    "daemon": thread.daemon,
                    "alive": thread.is_alive(),
                    "stack": stack
                })
        
        return {
            "thread_count": len(threads),
            "threads": thread_info
        }
    except Exception as e:
        return {"error": str(e)}

def get_file_metrics(file_path: str) -> Dict[str, Any]:
    """
    Get metrics for a file.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Dictionary with file metrics
    """
    try:
        path = Path(file_path)
        
        if not path.exists():
            return {"error": f"File not found: {file_path}"}
        
        if not path.is_file():
            return {"error": f"Not a file: {file_path}"}
        
        # Get file stats
        stat = path.stat()
        
        # Read file content to count lines
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            lines = content.splitlines()
            line_count = len(lines)
            
            # Count code lines (non-blank, non-comment)
            code_lines = 0
            for line in lines:
                stripped = line.strip()
                if stripped and not stripped.startswith('#') and not stripped.startswith('"""'):
                    code_lines += 1
        
        # Calculate hash of file content
        import hashlib
        file_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
        
        return {
            "path": str(path),
            "size_bytes": stat.st_size,
            "created_at": stat.st_ctime,
            "modified_at": stat.st_mtime,
            "total_lines": line_count,
            "code_lines": code_lines,
            "hash": file_hash,
            "exceeds_limit": line_count > 500  # Flag if file exceeds 500 lines
        }
    except Exception as e:
        return {"error": str(e)}

def generate_uuid() -> str:
    """
    Generate a UUID v4.
    
    Returns:
        String representation of a UUID v4
    """
    return str(uuid.uuid4())

def get_current_time(timezone: Optional[str] = None) -> Dict[str, Any]:
    """
    Get the current time in the specified timezone.
    
    Args:
        timezone: Timezone to use (e.g., 'UTC', 'US/Pacific')
        
    Returns:
        Dictionary with current time information
    """
    try:
        import datetime
        import pytz
        
        # Use UTC if timezone is not specified
        if timezone is None:
            timezone = 'UTC'
        
        # Get the timezone
        tz = pytz.timezone(timezone)
        
        # Get the current time
        now = datetime.datetime.now(tz)
        
        return {
            "timestamp": now.timestamp(),
            "iso8601": now.isoformat(),
            "formatted": now.strftime('%Y-%m-%d %H:%M:%S %Z'),
            "timezone": timezone,
            "utc_offset": now.utcoffset().total_seconds() / 3600
        }
    except Exception as e:
        return {
            "timestamp": time.time(),
            "error": str(e)
        }