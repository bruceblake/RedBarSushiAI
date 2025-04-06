# run.py
import os
import sys
from app import create_app

print(f"Starting app in {os.getcwd()}", file=sys.stderr)
print(f"Python version: {sys.version}", file=sys.stderr)
print(f"Python path: {sys.executable}", file=sys.stderr)
print(f"Environment: {os.environ.get('DOCKER', 'local')}", file=sys.stderr)

# Create the Flask application
try:
    app = create_app()
    print("Application created successfully", file=sys.stderr)
except Exception as e:
    print(f"ERROR creating application: {e}", file=sys.stderr)
    raise

# Add a simple route to test basic functionality
@app.route('/hello')
def hello():
    return {"message": "Hello from RedBarSushiAI\!"}

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
