#!/bin/bash
# Script to fix Pydantic version in Docker container

# Pin Pydantic to v1.x if it's not already installed
if ! pip show pydantic | grep -q "Version: 1."; then
    echo "Installing Pydantic v1.10.13 for compatibility..."
    pip uninstall -y pydantic
    pip install pydantic==1.10.13
    echo "Pydantic v1.10.13 installed successfully"
else
    echo "Pydantic v1.x already installed"
fi

# Install pydantic-settings if using v2
if pip show pydantic | grep -q "Version: 2."; then
    echo "Installing pydantic-settings for v2 compatibility..."
    pip install pydantic-settings
    echo "pydantic-settings installed successfully"
fi