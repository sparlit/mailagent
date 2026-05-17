import os
from dotenv import load_dotenv

load_dotenv()

CREDENTIALS_PATH = os.getenv('GMAIL_CREDENTIALS_PATH', 'credentials.json')
TOKEN_PATH = os.getenv('GMAIL_TOKEN_PATH', 'token.json')
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '300')) # Default 5 minutes
