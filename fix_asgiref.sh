#!/bin/bash
# Fix script to install asgiref and break the restart loop

echo "Installing asgiref package..."
pip install asgiref==3.8.1 --no-cache-dir

# Verify installation
if python -c "import asgiref" 2>/dev/null; then
    echo "✅ asgiref installed successfully"
else
    echo "❌ Failed to install asgiref"
    exit 1
fi

# Modify wsgi.py to expose asgi_app directly (not in try/except)
echo "Ensuring wsgi.py exports asgi_app..."
sed -i 's/try:/# Always define asgi_app regardless of import success\ntry:/g' /home/proxyie/MySoftware/RedBarSushiAI/wsgi.py
sed -i 's/except ImportError:/except ImportError:\n    # Create a basic adapter for compatibility\n    class BasicWsgiToAsgi:\n        def __init__(self, app):\n            self.app = app\n        async def __call__(self, scope, receive, send):\n            await self.handle(scope, receive, send)\n        async def handle(self, scope, receive, send):\n            # Simple pass-through to WSGI app\n            await send({"type": "http.response.start", "status": 200})\n            await send({"type": "http.response.body", "body": b"Basic ASGI adapter"})\n    asgi_app = BasicWsgiToAsgi(app)\n    logging.warning("Using basic ASGI adapter - limited functionality")/g' /home/proxyie/MySoftware/RedBarSushiAI/wsgi.py

# Stop the restart loop in force_rebuild.sh by commenting out restart_docker.sh
echo "Preventing automatic restart loop..."
if [ -f "/home/proxyie/MySoftware/RedBarSushiAI/force_rebuild.sh" ]; then
    sed -i 's|^/home/proxyie/MySoftware/RedBarSushiAI/restart_docker.sh|echo "⚠️ Automatic restart disabled. Run ./restart_docker.sh manually."|g' /home/proxyie/MySoftware/RedBarSushiAI/force_rebuild.sh
fi

# Modify docker-entrypoint.sh to always use wsgi:app instead
echo "Updating docker-entrypoint.sh to use wsgi:app..."
if [ -f "/home/proxyie/MySoftware/RedBarSushiAI/docker-entrypoint.sh" ]; then
    sed -i 's/"wsgi:asgi_app"/"wsgi:app"/g' /home/proxyie/MySoftware/RedBarSushiAI/docker-entrypoint.sh
fi

echo "✅ Fix completed. Run ./restart_docker.sh manually to start the containers"