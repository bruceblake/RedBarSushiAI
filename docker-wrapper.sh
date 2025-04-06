#!/bin/bash
# Debugging wrapper script
echo "Starting wrapper script at $(date)" > /tmp/docker_debug.log
echo "Environment variables:" >> /tmp/docker_debug.log
env | sort >> /tmp/docker_debug.log

# Run the real entrypoint script and capture both stdout and stderr
echo "Running docker-entrypoint.sh" >> /tmp/docker_debug.log
/home/proxyie/MySoftware/RedBarSushiAI/docker-entrypoint.sh 2>&1 | tee -a /tmp/docker_debug.log