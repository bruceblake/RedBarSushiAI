#!/bin/bash
# Quick fix for X11 display environment variables
set -e

echo "===== Setting up X11 display environment variables ====="

# Configure display to use :2 as suggested by diagnostic output
export DISPLAY=:2

# Set environment variables for OpenAI Realtime client
export PYNPUT_HEADLESS=0
export NO_X11=0
export HEADLESS=0
export OPENAI_REALTIME_NO_DISPLAY=0
export X11_SETUP_SUCCESS=true
export OPENAI_REALTIME_AVAILABLE=1
export USE_XVFB=true

# Save to .bashrc
echo "# Added by RedBarSushiAI fix script" >> ~/.bashrc
echo "export DISPLAY=$DISPLAY" >> ~/.bashrc
echo "export PYNPUT_HEADLESS=0" >> ~/.bashrc
echo "export NO_X11=0" >> ~/.bashrc
echo "export HEADLESS=0" >> ~/.bashrc
echo "export OPENAI_REALTIME_NO_DISPLAY=0" >> ~/.bashrc
echo "export X11_SETUP_SUCCESS=true" >> ~/.bashrc
echo "export OPENAI_REALTIME_AVAILABLE=1" >> ~/.bashrc
echo "export USE_XVFB=true" >> ~/.bashrc

# Create a setup file that can be sourced in Dockerfile or docker-entrypoint.sh
cat > ~/x11_env.sh << EOF
#!/bin/bash
export DISPLAY=$DISPLAY
export PYNPUT_HEADLESS=0
export NO_X11=0
export HEADLESS=0
export OPENAI_REALTIME_NO_DISPLAY=0
export X11_SETUP_SUCCESS=true
export OPENAI_REALTIME_AVAILABLE=1
export USE_XVFB=true
EOF

chmod +x ~/x11_env.sh

echo "✅ X11 environment variables set to use display $DISPLAY"
echo "✅ Created environment setup script at ~/x11_env.sh"
echo ""
echo "To use in Docker, add this to your Dockerfile:"
echo "COPY x11_env.sh /app/"
echo "RUN chmod +x /app/x11_env.sh"
echo "RUN source /app/x11_env.sh"
echo ""
echo "Or add to your docker-entrypoint.sh:"
echo "source /app/x11_env.sh"