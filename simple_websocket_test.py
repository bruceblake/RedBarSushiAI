#!/usr/bin/env python3
"""
Simple WebSocket test server to verify WebSocket implementation.
"""

from flask import Flask
from flask_sock import Sock

app = Flask(__name__)
sock = Sock(app)

@sock.route('/ws/test')
def ws_test(ws):
    """Simple WebSocket echo test endpoint"""
    ws.send('Welcome to WebSocket test')
    while True:
        data = ws.receive()
        if data:
            print(f"Received: {data}")
            ws.send(f"Echo: {data}")

@app.route('/healthcheck')
def healthcheck():
    """Simple healthcheck endpoint"""
    return {"status": "ok", "message": "WebSocket test server running"}

if __name__ == '__main__':
    print("Starting WebSocket test server on port 8081...")
    from gevent import pywsgi
    from geventwebsocket.handler import WebSocketHandler
    server = pywsgi.WSGIServer(('0.0.0.0', 8081), app, handler_class=WebSocketHandler)
    server.serve_forever()