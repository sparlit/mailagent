import os
import json
from dotenv import load_dotenv

load_dotenv()

# ACCOUNTS_JSON should be a string containing a list of objects:
# [{"credentials": "creds1.json", "token": "token1.json"}, ...]
ACCOUNTS_JSON = os.getenv('GMAIL_ACCOUNTS', '[{"credentials": "credentials.json", "token": "token.json"}]')
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '300'))
MAX_WORKERS = int(os.getenv('MAX_WORKERS', '10'))
RULES_PATH = os.getenv('RULES_PATH', 'rules.json')
DASHBOARD_ENABLED = os.getenv('DASHBOARD_ENABLED', 'True').lower() == 'true'
DASHBOARD_PORT = int(os.getenv('DASHBOARD_PORT', '5000'))
DRY_RUN = os.getenv('DRY_RUN', 'False').lower() == 'true'

def get_accounts():
    """
    Parse the configured ACCOUNTS_JSON and produce a list of account mappings.
    
    If ACCOUNTS_JSON contains valid JSON, returns its parsed value. If parsing fails, returns a fallback list containing a single account mapping with default credential and token file names.
    
    Returns:
        list[dict]: List of account objects; on parse failure, [{"credentials": "credentials.json", "token": "token.json"}].
    """
    try:
        return json.loads(ACCOUNTS_JSON)
    except json.JSONDecodeError:
        return [{"credentials": "credentials.json", "token": "token.json"}]
