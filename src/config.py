import os
import json
from dotenv import load_dotenv

load_dotenv()

# ACCOUNTS_JSON should be a string containing a list of objects:
# [{"credentials": "creds1.json", "token": "token1.json"}, ...]
ACCOUNTS_JSON = os.getenv('GMAIL_ACCOUNTS', '[{"credentials": "credentials.json", "token": "token.json"}]')
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '1800'))
MAX_WORKERS = int(os.getenv('MAX_WORKERS', '10'))
RULES_PATH = os.getenv('RULES_PATH', 'rules.json')

DASHBOARD_ENABLED = os.getenv('DASHBOARD_ENABLED', 'True').lower() == 'true'
DASHBOARD_PORT = int(os.getenv('DASHBOARD_PORT', '5000'))
DRY_RUN = os.getenv('DRY_RUN', 'False').lower() == 'true'

def get_accounts():
    try:
        return json.loads(ACCOUNTS_JSON)
    except json.JSONDecodeError:
        return [{"credentials": "credentials.json", "token": "token.json"}]
