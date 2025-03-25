# app/config.py
import os

# ------------------------------
# General Application Settings
# ------------------------------
APP_SECRET_KEY = "bd0acf5c060feaa576051293a661a49a"

# ------------------------------
# Database Configuration
# ------------------------------
SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://pegasus:Redbar2024!!@pegasus.mysql.pythonanywhere-services.com/pegasus$CALLER_INFORMATION'
SQLALCHEMY_TRACK_MODIFICATIONS = False

# ------------------------------
# Ngrok & Twilio Configuration
# ------------------------------
NGROK_AUTHTOKEN = "2TPx8vjcOGWQiJj5x3rgkJ09uQ0_6krep2WJjqsNyzMedv4ew"

TWILIO_ACCOUNT_SID = "ACb8391ed8d92871d85180ca9adea481b6"
TWILIO_API_KEY_SID = "SK55c8d2ec3e662acffb868fcc42ed75ac"
TWILIO_API_SECRET = "Ky6uApOQMFAZKCbhe5aaZkyGIBzdIRMT"
TWILIO_AUTH_TOKEN = "d4830ea0bb52ffdb63620c2333fcdd59"
TWILIO_NUMBER = "+18333247207"

# ------------------------------
# AssemblyAI (if used)
# ------------------------------
ASSEMBLYAI_API_KEY = "a116ce3f35164bd78f295ddd6ccd7ee0"

# ------------------------------
# OpenAI Configuration
# ------------------------------
OPENAI_API_KEY = "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"

# ------------------------------
# Stripe Configuration
# ------------------------------
STRIPE_API_KEY = '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'
STRIPE_PRODUCT_ID = 'prod_QbXflydy7HavBH'

# ------------------------------
# Deliverect Configuration
# ------------------------------
DELIVERECT_CLIENT_ID = 'w2ajqOd1CMUsRBPF'
DELIVERECT_CLIENT_SECRET = 'byOTwZy7CvhgFgQBuvdGVZVcWoxlfTj1'
DELIVERECT_API_URL = 'https://api.staging.deliverect.com/nextgen/order/66e88f33475a66c53e90e62b'

# ------------------------------
# Local File Paths
# ------------------------------
MENU_FILE_PATH = os.getenv("MENU_FILE_PATH", "/home/pegasus/mysite/RedBarSushiAI/menu_data.json")

# Add a more robust fallback to account for deployment paths
if not os.path.exists(MENU_FILE_PATH):
    # Try to find the menu_data.json in the current directory or parent directories
    current_dir = os.path.dirname(os.path.abspath(__file__))
    potential_paths = [
        os.path.join(current_dir, 'menu_data.json'),
        os.path.join(os.path.dirname(current_dir), 'menu_data.json'),
        os.path.join(os.path.dirname(os.path.dirname(current_dir)), 'menu_data.json'),
        "/home/proxyie/MySoftware/RedBarSushiAI/menu_data.json"  # Local dev path
    ]
    
    for path in potential_paths:
        if os.path.exists(path):
            MENU_FILE_PATH = path
            break

# ------------------------------
# Base URL Configuration
# ------------------------------
BASE_URL = os.environ.get('BASE_URL', 'https://redbarsushi.pythonanywhere.com')
