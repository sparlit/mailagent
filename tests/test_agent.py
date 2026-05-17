import pytest
import json
import os
import sqlite3
import base64
from unittest.mock import MagicMock, patch, PropertyMock
from src.classifier import EmailClassifier
from src.agent import MailAgent
from src.database import Database
from src.bayesian_filter import BayesianFilter

@pytest.fixture
def rules_file(tmp_path):
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
    return EmailClassifier(rules_path=rules_file)

@pytest.fixture
def db(tmp_path):
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
    assert stats[0][0] == "test@example.com"
    assert stats[0][1] == "label"

def test_bayesian_filter():
    filter = BayesianFilter(model_path=':memory:')
    filter.train("win free money now", is_spam=True)
    filter.train("hello friend how are you", is_spam=False)

    spam_prob = filter.predict("win money")
    ham_prob = filter.predict("hello friend")

    assert spam_prob > 0.5
    assert ham_prob < 0.5

def test_gmail_client_body_extraction():
    from src.gmail_client import GmailClient

    # Mock service
    mock_service = MagicMock()

    payload = {
        'parts': [
            {
                'mimeType': 'text/plain',
                'body': {'data': base64.urlsafe_b64encode(b"Hello World").decode()}
            }
        ]
    }

    with patch.object(GmailClient, '_load_credentials'), \
         patch.object(GmailClient, 'service', new_callable=PropertyMock) as mock_service_prop, \
         patch.object(GmailClient, '_get_user_email', return_value="test@example.com"):

        mock_service_prop.return_value = mock_service
        client = GmailClient()

        body = client._get_body(payload)
        assert body == "Hello World"

def test_database_account_management(db):
    db.add_account("user@example.com", credentials_path="creds.json", token_path="token.json")
    accounts = db.get_accounts()
    assert len(accounts) == 1
    assert accounts[0]['email'] == "user@example.com"

    db.update_account_token("user@example.com", '{"token": "new"}')
    accounts = db.get_accounts()
    assert accounts[0]['token_json'] == '{"token": "new"}'

def test_dashboard_health_endpoint():
    from src.dashboard import app
    with app.test_client() as client:
        response = client.get('/health')
        assert response.status_code == 200
        assert response.get_json() == {"status": "healthy"}
