# wsgi.py - Alternative entry point for WSGI servers

from run import app as application

# Gunicorn looks for an 'application' object by default
if __name__ == "__main__":
    application.run()
