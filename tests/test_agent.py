import pytest
import json
import os
import sqlite3
from unittest.mock import MagicMock, patch, PropertyMock
from src.classifier import EmailClassifier
from src.agent import MailAgent
from src.database import Database

@pytest.fixture
def rules_file(tmp_path):
    """
    Create a temporary rules.json file with sample email classification rules and return its path.
    
    Parameters:
        tmp_path (pathlib.Path): pytest temporary directory in which the rules.json will be created.
    
    Returns:
        str: Filesystem path to the created rules.json file.
    """
    rules = {
        "SPAM": {
            "patterns": ["win money"],
            "header_rules": [{"name": "X-Spam", "pattern": "YES"}],
            "actions": ["trash"]
        },
        "SOCIAL": {
            "patterns": ["facebook"],
            "actions": ["label", "mark_read"]
        }
    }
    rules_path = tmp_path / "rules.json"
    rules_path.write_text(json.dumps(rules))
    return str(rules_path)

@pytest.fixture
def classifier(rules_file):
    """
    Create an EmailClassifier configured from a rules file.
    
    Parameters:
        rules_file (str): Path to a JSON rules file that defines classification rules.
    
    Returns:
        EmailClassifier: Instance configured to use the rules at `rules_file`.
    """
    return EmailClassifier(rules_path=rules_file)

@pytest.fixture
def db(tmp_path):
    """
    Create a temporary SQLite-backed Database instance for tests.
    
    Returns:
        Database: A Database connected to a `test.db` file located inside the provided `tmp_path`.
    """
    db_path = tmp_path / "test.db"
    return Database(db_path=str(db_path))

def test_classify_header_rules(classifier):
    message = {
        'snippet': 'normal text',
        'payload': {'headers': [{'name': 'X-Spam', 'value': 'YES'}]}
    }
    category, actions = classifier.classify(message)
    assert category == 'SPAM'
    assert actions == ['trash']

def test_agent_records_stats(db):
    mock_client = MagicMock()
    mock_client.email_address = "test@example.com"
    mock_client.list_unread_messages.return_value = [{'id': 'msg1'}]
    mock_client.get_message.return_value = {
        'id': 'msg1',
        'snippet': 'text',
        'payload': {'headers': [{'name': 'Subject', 'value': 'test'}]}
    }

    mock_classifier = MagicMock()
    mock_classifier.classify.return_value = ('SOCIAL', ['label'])

    agent = MailAgent([mock_client], mock_classifier, db)
    agent.run_once()

    stats = db.get_stats()
    assert len(stats) > 0
    # (account, action, category, count)
    assert stats[0][0] == "test@example.com"
    assert stats[0][1] == "label"
    assert stats[0][2] == "SOCIAL"
    assert stats[0][3] == 1

def test_gmail_client_env_credentials():
    from src.gmail_client import GmailClient
    token_data = {
        "token": "fake-token",
        "refresh_token": "fake-refresh",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "fake-id",
        "client_secret": "fake-secret",
        "scopes": ["https://www.googleapis.com/auth/gmail.modify"],
        "expiry": "2099-01-01T00:00:00Z"
    }

    with patch.dict(os.environ, {"GMAIL_TOKEN_TOKEN_JSON": json.dumps(token_data)}), \
         patch("os.path.exists", side_effect=lambda x: x == "credentials.json"), \
         patch("src.gmail_client.build"), \
         patch.object(GmailClient, '_get_user_email', return_value="test@example.com"):
        client = GmailClient(token_path="token.json")
        assert client._creds.token == "fake-token"
