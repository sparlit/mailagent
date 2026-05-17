import pytest
from unittest.mock import MagicMock
from src.classifier import EmailClassifier
from src.agent import MailAgent

@pytest.fixture
def classifier():
    return EmailClassifier()

def test_classify_spam(classifier):
    message = {
        'snippet': 'Congratulations! You won a lottery prize.',
        'payload': {'headers': [{'name': 'Subject', 'value': 'You won'}]}
    }
    assert classifier.classify(message) == 'SPAM'

def test_classify_social(classifier):
    message = {
        'snippet': 'You have a new friend request',
        'payload': {'headers': [{'name': 'From', 'value': 'Facebook <no-reply@facebook.com>'}]}
    }
    assert classifier.classify(message) == 'SOCIAL'

def test_classify_updates(classifier):
    message = {
        'snippet': 'Your order has been shipped',
        'payload': {'headers': [{'name': 'Subject', 'value': 'Shipping Update'}]}
    }
    assert classifier.classify(message) == 'UPDATES'

def test_classify_inbox(classifier):
    message = {
        'snippet': 'Hello, how are you?',
        'payload': {'headers': [{'name': 'From', 'value': 'friend@example.com'}]}
    }
    assert classifier.classify(message) == 'INBOX'

def test_agent_run_once_no_messages():
    mock_gmail = MagicMock()
    mock_gmail.list_unread_messages.return_value = []
    mock_classifier = MagicMock()

    agent = MailAgent(mock_gmail, mock_classifier)
    agent.run_once()

    mock_gmail.list_unread_messages.assert_called_once()
    mock_gmail.get_message.assert_not_called()

def test_agent_processes_spam():
    mock_gmail = MagicMock()
    mock_gmail.list_unread_messages.return_value = [{'id': '123'}]
    mock_gmail.get_message.return_value = {'id': '123', 'snippet': 'spam'}

    mock_classifier = MagicMock()
    mock_classifier.classify.return_value = 'SPAM'

    agent = MailAgent(mock_gmail, mock_classifier)
    agent.run_once()

    mock_gmail.move_to_trash.assert_called_with('123')
