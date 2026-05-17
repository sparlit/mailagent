import pytest
import json
import os
from unittest.mock import MagicMock, patch, PropertyMock
from src.classifier import EmailClassifier
from src.agent import MailAgent

@pytest.fixture
def rules_file(tmp_path):
    rules = {
        "SPAM": ["win money"],
        "SOCIAL": ["facebook"],
        "UPDATES": ["invoice"]
    }
    rules_path = tmp_path / "rules.json"
    rules_path.write_text(json.dumps(rules))
    return str(rules_path)

@pytest.fixture
def classifier(rules_file):
    return EmailClassifier(rules_path=rules_file)

def test_classify_dynamic_rules(classifier):
    message = {
        'snippet': 'You win money now!',
        'payload': {'headers': [{'name': 'Subject', 'value': 'Hello'}]}
    }
    assert classifier.classify(message) == 'SPAM'

def test_agent_processes_multi_account():
    mock_client1 = MagicMock()
    mock_client2 = MagicMock()

    mock_client1.list_unread_messages.return_value = [{'id': 'msg1'}]
    mock_client2.list_unread_messages.return_value = [{'id': 'msg2'}]

    mock_client1.get_message.return_value = {'id': 'msg1', 'snippet': 'text'}
    mock_client2.get_message.return_value = {'id': 'msg2', 'snippet': 'text'}

    mock_classifier = MagicMock()
    mock_classifier.classify.return_value = 'INBOX'

    agent = MailAgent([mock_client1, mock_client2], mock_classifier)
    agent.run_once()

    assert mock_client1.list_unread_messages.call_count == 1
    assert mock_client2.list_unread_messages.call_count == 1
    assert mock_client1.get_message.call_count == 1
    assert mock_client2.get_message.call_count == 1

def test_gmail_client_pagination():
    mock_service = MagicMock()
    # Mocking self.service.users().messages().list().execute()
    mock_list_call = mock_service.users().messages().list

    # First page
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
        assert messages[0]['id'] == '1'
        assert messages[1]['id'] == '2'
