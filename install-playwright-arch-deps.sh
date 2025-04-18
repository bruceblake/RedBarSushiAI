#!/bin/bash
# Script to install Playwright system dependencies on Arch Linux

echo "Installing Playwright system dependencies for Arch Linux..."

# These packages correspond to the Ubuntu dependencies Playwright wants to install
# but mapped to their Arch Linux equivalents
sudo pacman -Syu --needed --noconfirm \
    nss \
    nspr \
    atk \
    at-spi2-atk \
    cups \
    libx11 \
    libxcomposite \
    libxdamage \
    libxext \
    libxfixes \
    libxrandr \
    mesa \
    libxcb \
    libxkbcommon \
    pango \
    cairo \
    alsa-lib \
    at-spi2-core \
    libdrm \
    libxshmfence \
    glib2 \
    gtk3 \
    libcups

echo "Setting environment variable to skip host validation..."
echo "export PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1" >> ~/.bashrc
echo "export PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1" >> venv/bin/activate

echo "Playwright system dependencies installed!"
echo "Please run 'source venv/bin/activate' to activate the virtual environment with the skipped validation."