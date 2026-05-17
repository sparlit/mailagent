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

def get_accounts():
    """
    Parse the ACCOUNTS_JSON environment value and return it as a list of account mappings.
    
    Returns:
        list[dict]: A list of account objects parsed from ACCOUNTS_JSON; each object contains at least the keys `"credentials"` and `"token"`. If ACCOUNTS_JSON is not valid JSON, returns a fallback list with a single account: `{"credentials": "credentials.json", "token": "token.json"}`.
    """
    try:
        return json.loads(ACCOUNTS_JSON)
    except json.JSONDecodeError:
        return [{"credentials": "credentials.json", "token": "token.json"}]
