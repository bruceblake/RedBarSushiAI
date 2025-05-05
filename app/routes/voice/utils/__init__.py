"""
Voice-specific utilities for the RedBarSushiAI application.

This package contains utility modules for voice processing,
including VAD configuration, diagnostics, and tool registry.
"""

from app.routes.voice.utils.tools_registry import ToolRegistry, register_default_tools
from app.routes.voice.utils.vad import configure_vad_for_context

# Export the utility classes and functions
__all__ = [
    "ToolRegistry", 
    "register_default_tools",
    "configure_vad_for_context"
]