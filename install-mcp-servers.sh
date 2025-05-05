#!/bin/bash

# Sequential Thinking
claude mcp add sequential-thinking -s user -- npx -y u/modelcontextprotocol/server-sequential-thinking

# Filesystem
claude mcp add filesystem -s user -- npx -y u/modelcontextprotocol/server-filesystem ~/Documents ~/Desktop ~/Downloads ~/Projects

# Puppeteer
claude mcp add puppeteer -s user -- npx -y u/modelcontextprotocol/server-puppeteer

# Web Fetching
claude mcp add fetch -s user -- npx -y u/kazuph/mcp-fetch

# Browser Tools
claude mcp add browser-tools -s user -- npx -y u/agentdeskai/browser-tools-mcp@1.2.1

# Check whats been installed
claude mcp list
