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
    rules = {
        "SPAM": {
            "patterns": ["win money"],
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

def test_classify_dynamic_rules(classifier):
    message = {
        'snippet': 'You win money now!',
        'payload': {'headers': [{'name': 'Subject', 'value': 'Hello'}]}
    }
    category, actions = classifier.classify(message)
    assert category == 'SPAM'
    assert actions == ['trash']

def test_agent_processes_multi_account(db):
    mock_client1 = MagicMock()
    mock_client1.list_unread_messages.return_value = [{'id': 'msg1'}]
    mock_client1.get_message.return_value = {'id': 'msg1', 'snippet': 'text'}

    mock_classifier = MagicMock()
    mock_classifier.classify.return_value = ('INBOX', [])

    agent = MailAgent([mock_client1], mock_classifier, db)
    agent.run_once()

    assert mock_client1.list_unread_messages.call_count == 1
    assert mock_client1.get_message.call_count == 1
    assert db.is_processed('msg1')

def test_agent_skips_processed(db):
    db.mark_as_processed('msg_already_done')

    mock_client = MagicMock()
    mock_client.list_unread_messages.return_value = [{'id': 'msg_already_done'}]

    mock_classifier = MagicMock()

    agent = MailAgent([mock_client], mock_classifier, db)
    agent.run_once()

    mock_client.get_message.assert_not_called()

def test_gmail_client_pagination():
    mock_service = MagicMock()
    mock_list_call = mock_service.users().messages().list

    mock_list_call.return_value.execute.side_effect = [
        {'messages': [{'id': '1'}], 'nextPageToken': 'token2'},
        {'messages': [{'id': '2'}]}
    ]

    from src.gmail_client import GmailClient
    with patch.object(GmailClient, '_load_credentials'), \
         patch.object(GmailClient, 'service', new_callable=PropertyMock) as mock_service_prop:
        mock_service_prop.return_value = mock_service
        client = GmailClient()
        messages = client.list_unread_messages()

        assert len(messages) == 2
