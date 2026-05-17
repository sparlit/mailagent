import pytest
from unittest.mock import MagicMock, patch
from src.classifier import EmailClassifier
from src.agent import MailAgent

@pytest.fixture
def classifier():
    return EmailClassifier()

def test_classify_spam(classifier):
    # Test with new regex patterns
    message = {
        'snippet': 'Congratulations! You won a lottery prize.',
        'payload': {'headers': [{'name': 'Subject', 'value': 'You won'}]}
    }
    assert classifier.classify(message) == 'SPAM'

    message2 = {
        'snippet': 'Your crypto giveaway is here',
        'payload': {'headers': [{'name': 'Subject', 'value': 'Airdrop'}]}
    }
    assert classifier.classify(message2) == 'SPAM'

def test_classify_social(classifier):
    message = {
        'snippet': 'You have a new friend request',
        'payload': {'headers': [{'name': 'From', 'value': 'Facebook <no-reply@facebook.com>'}]}
    }
    assert classifier.classify(message) == 'SOCIAL'

    message2 = {
        'snippet': 'Check out this TikTok',
        'payload': {'headers': [{'name': 'From', 'value': 'TikTok <trending@tiktok.com>'}]}
    }
    assert classifier.classify(message2) == 'SOCIAL'

def test_classify_updates(classifier):
    message = {
        'snippet': 'Your order has been shipped',
        'payload': {'headers': [{'name': 'Subject', 'value': 'Shipping Update'}]}
    }
    assert classifier.classify(message) == 'UPDATES'

    message2 = {
        'snippet': 'Your monthly statement is ready',
        'payload': {'headers': [{'name': 'Subject', 'value': 'Bill'}]}
    }
    assert classifier.classify(message2) == 'UPDATES'

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

def test_agent_processes_spam_parallel():
    mock_gmail = MagicMock()
    mock_gmail.list_unread_messages.return_value = [{'id': '123'}, {'id': '456'}]
    mock_gmail.get_message.side_effect = [
        {'id': '123', 'snippet': 'spam'},
        {'id': '456', 'snippet': 'ham'}
    ]

    mock_classifier = MagicMock()
    mock_classifier.classify.side_effect = ['SPAM', 'INBOX']

    agent = MailAgent(mock_gmail, mock_classifier, max_workers=2)
    agent.run_once()

    assert mock_gmail.get_message.call_count == 2
    mock_gmail.move_to_trash.assert_any_call('123')
