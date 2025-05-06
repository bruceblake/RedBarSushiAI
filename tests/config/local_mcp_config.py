#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Configuration for local MCP testing.
"""

import os

# Local MCP server URL
MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://localhost:4000/mcp")

# Test database URL (for local testing)
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/redbarsushi")

# Test Redis URL (for local testing)
TEST_REDIS_URL = os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/0")

# Test configuration
TEST_CONFIG = {
    "environment": "local",
    "mcp_server": MCP_SERVER_URL,
    "database": TEST_DATABASE_URL,
    "redis": TEST_REDIS_URL,
    "protocol_version": os.environ.get("MCP_PROTOCOL_VERSION", "2024-11-05")
}

# MCP Tool Types
class TestType:
    BASIC = "basic"
    DATABASE = "database"
    REDIS = "redis"
    MENU = "menu"
    ORDER = "order"
    FULL_MENU = "full_menu"
    FULL_ORDER = "full_order"
    ALL = "all"

# MCP Error Codes (JSON-RPC 2.0 standard errors)
class ErrorCode:
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    # Server defined errors
    TOOL_NOT_FOUND = -32001
    TOOL_EXECUTION_ERROR = -32002