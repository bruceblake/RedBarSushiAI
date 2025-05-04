# Using Claude Code as an MCP Server

This document explains how to use Claude Code itself as an MCP (Model Context Protocol) server for the RedBarSushiAI project.

## Overview

Claude Code includes a built-in MCP server capability that allows other applications to connect to it and use Claude's tools and capabilities. This approach is simpler and more reliable than creating a custom MCP server.

## Running Claude Code as an MCP Server

To use Claude Code as an MCP server:

1. Start Claude Code in MCP server mode:
   ```bash
   claude mcp serve
   ```

   This will start Claude Code as an MCP server that other applications can connect to.

2. In another terminal window, you can then access Claude with your regular workflow.

## Connecting from Another Application

You can connect to the Claude Code MCP server from any MCP client. Here's an example configuration for Claude Desktop:

```json
{
  "command": "claude",
  "args": ["mcp", "serve"],
  "env": {}
}
```

## Available Tools

When using Claude Code as an MCP server, clients will have access to all of Claude's built-in tools, including:

- **File Operations**: Read, Write, Edit, LS, Glob, etc.
- **Code Analysis**: Grep, Search, etc.
- **Environment Tools**: Bash, etc.

## Benefits of Using Claude Code as MCP Server

1. **Reliability**: Uses Claude's official implementation of the MCP protocol
2. **Full Tool Access**: Provides access to all of Claude's built-in tools
3. **Automatic Updates**: Benefits from automatic updates to the protocol and tools
4. **Simplified Setup**: No need to create and maintain a custom MCP server

## Testing the RedBarSushiAI Project

To test the RedBarSushiAI project using Claude Code as an MCP server:

1. Start Claude Code as an MCP server:
   ```bash
   claude mcp serve
   ```

2. Use a client that supports MCP to connect to the server. For example, use Claude Desktop.

3. From the connected client, you can request operations like:
   - "Show me the status of the staging environment"
   - "Run connectivity tests on the staging environment"
   - "Check the logs for any errors"
   - "Run E2E tests for the voice module"

The connected client will use Claude's capabilities to execute these operations and return the results.

## Security Considerations

When using Claude Code as an MCP server:

1. The MCP client will have access to the same permissions as Claude Code
2. Be cautious about which clients you allow to connect to your Claude Code MCP server
3. Clients are responsible for implementing user confirmation for individual tool calls

## Troubleshooting

If you encounter issues:

1. Ensure Claude Code is running in MCP server mode with `claude mcp serve`
2. Check that the client configuration correctly points to the Claude Code MCP server
3. Verify that the client implements the MCP protocol correctly
4. Look for error messages in the Claude Code MCP server output

## Conclusion

Using Claude Code as an MCP server provides a simple and reliable way to give other applications access to Claude's capabilities for testing and interacting with the RedBarSushiAI project. This approach leverages Claude's built-in tools and official MCP implementation.