import os
import json
from dotenv import load_dotenv

load_dotenv()

__all__ = [
    'ACCOUNTS_JSON',
    'CHECK_INTERVAL',
    'MAX_WORKERS',
    'RULES_PATH',
    'DRY_RUN',
    'DASHBOARD_ENABLED',
    'DASHBOARD_PORT',
    'get_accounts'
]

def get_bool_env(key, default):
    val = os.getenv(key, str(default)).lower()
    return val in ('true', '1', 't', 'y', 'yes')

# ACCOUNTS_JSON should be a string containing a list of objects:
# [{"credentials": "creds1.json", "token": "token1.json"}, ...]
ACCOUNTS_JSON = os.getenv('GMAIL_ACCOUNTS', '[{"credentials": "credentials.json", "token": "token.json"}]')
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '1800'))
MAX_WORKERS = int(os.getenv('MAX_WORKERS', '10'))
RULES_PATH = os.getenv('RULES_PATH', 'rules.json')
DRY_RUN = get_bool_env('DRY_RUN', False)
DASHBOARD_ENABLED = get_bool_env('DASHBOARD_ENABLED', True)
DASHBOARD_PORT = int(os.getenv('DASHBOARD_PORT', '5000'))

def get_accounts():
    """
    Parse the ACCOUNTS_JSON environment variable into a list of account dictionaries.
    
    Returns:
        list: Parsed list of account dicts from ACCOUNTS_JSON. If ACCOUNTS_JSON is not valid JSON, returns a default list containing one account: {"credentials": "credentials.json", "token": "token.json"}.
    """
    try:
        return json.loads(ACCOUNTS_JSON)
    except json.JSONDecodeError:
        return [{"credentials": "credentials.json", "token": "token.json"}]
