import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from src.agent import MailAgent
from src.classifier import EmailClassifier
from src.gmail_client import GmailClient

def test_forward_action_execution():
    client = MagicMock(spec=GmailClient)
    client.email_address = "agent@example.com"
    db = MagicMock()
    classifier = MagicMock()

    agent = MailAgent([client], classifier, db, dry_run=False)

    agent.execute_actions(client, "msg123", "WORK", ["forward:boss@example.com"])

    client.forward_message.assert_called_once_with("msg123", "boss@example.com")

def test_ml_fallback_classification(tmp_path):
    rules = {
        "SPAM": {
            "patterns": ["win money", "lottery"],
            "actions": ["trash"]
        },
        "WORK": {
            "patterns": ["meeting", "deadline"],
            "actions": ["label"]
        }
    }
    rules_path = tmp_path / "rules.json"
    import json
    rules_path.write_text(json.dumps(rules))

    classifier = EmailClassifier(rules_path=str(rules_path))

    # This message doesn't match regex exactly but has 'money' which is in SPAM patterns
    # Regex for "win money" won't match "some money"
    message = {
        'snippet': 'you have some money waiting',
        'payload': {'headers': []}
    }

    category, actions = classifier.classify(message)
    assert category == "SPAM"
    assert actions == ["trash"]

def test_gmail_client_forward_message_api_call():
    with patch("src.gmail_client.GmailClient._load_credentials", return_value=MagicMock()), \
         patch("src.gmail_client.GmailClient._get_user_email", return_value="me@example.com"):

        client = GmailClient()
        # Mock the service property directly
        mock_service = MagicMock()
        with patch.object(GmailClient, 'service', new_callable=PropertyMock) as mock_service_prop:
            mock_service_prop.return_value = mock_service

            client.get_message = MagicMock(return_value={
                'snippet': 'test snippet',
                'payload': {'headers': [{'name': 'Subject', 'value': 'Hello'}]}
            })

            client.forward_message("m1", "to@example.com")

            mock_service.users.assert_called()
            mock_service.users().messages.assert_called()

def test_body_extraction():
    client = GmailClient.__new__(GmailClient)
    payload = {
        'mimeType': 'multipart/mixed',
        'parts': [
            {
                'mimeType': 'text/plain',
                'body': {'data': 'SGVsbG8gd29ybGQ='} # "Hello world" base64
            },
            {
                'mimeType': 'multipart/alternative',
                'parts': [
                    {
                        'mimeType': 'text/plain',
                        'body': {'data': 'U2Vjb25kIHBhcnQ='} # "Second part" base64
                    }
                ]
            }
        ]
    }
    body = client._get_body_text(payload)
    assert "Hello world" in body
    assert "Second part" in body

def test_reply_action_execution():
    client = MagicMock(spec=GmailClient)
    client.email_address = "agent@example.com"
    db = MagicMock()
    classifier = MagicMock()

    agent = MailAgent([client], classifier, db, dry_run=False)

    # Mock templates
    with patch("builtins.open", MagicMock(side_effect=[
        MagicMock(__enter__=lambda self: self, __exit__=lambda *args: None, read=lambda: '{"test_tpl": {"subject": "Re: {subject}", "body": "Hello!"}}')
    ])), patch("os.path.exists", return_value=True):

        client.get_message.return_value = {
            'payload': {'headers': [{'name': 'Subject', 'value': 'Original Subject'}]}
        }

        agent.execute_actions(client, "msg123", "WORK", ["reply:test_tpl"])

        client.send_reply.assert_called_once_with("msg123", "Re: Original Subject", "Hello!")
