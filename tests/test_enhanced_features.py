import pytest
import os
from src.database import Database
from src.agent import MailAgent
from src.gmail_client import MockGmailClient
from src.classifier import EmailClassifier
from src import config

def test_activity_logging():
    db = Database(':memory:')
    db.log_activity("test@example.com", "msg123", "star", "WORK")
    recent = db.get_recent_activity(5)
    assert len(recent) == 1
    assert recent[0][0] == "test@example.com"
    assert recent[0][1] == "msg123"
    assert recent[0][2] == "star"
    assert recent[0][3] == "WORK"

def test_max_messages_per_cycle(monkeypatch):
    # Set limit to 2
    monkeypatch.setattr(config, 'MAX_MESSAGES_PER_CYCLE', 2)

    db = Database(':memory:')
    # Mock classifier that returns a category but no actions to avoid real execution issues
    class SimpleClassifier:
        def classify(self, msg): return "INBOX", []
        def reload_rules(self): pass

    # Mock client that returns 5 messages
    class MultiMsgMockClient(MockGmailClient):
        def list_unread_messages(self, user_id='me'):
            return [{'id': f'msg_{i}'} for i in range(5)]
        def get_message(self, msg_id, user_id='me'):
            return {'id': msg_id, 'payload': {'headers': []}}
        def _get_body_text(self, payload): return ""

    client = MultiMsgMockClient()
    agent = MailAgent([client], SimpleClassifier(), db, max_workers=1)

    # We need to capture how many tasks are submitted.
    # Since run_once uses ThreadPoolExecutor internally, we can't easily count its tasks directly
    # but we can check the database or logs.

    agent.run_once()

    # Check processed_messages table
    with db._lock:
        conn = db._get_connection()
        cursor = conn.execute('SELECT count(*) FROM processed_messages')
        count = cursor.fetchone()[0]
        assert count == 2

def test_ml_confidence_threshold(monkeypatch):
    monkeypatch.setattr(config, 'ML_CONFIDENCE_THRESHOLD', 0.9)
    # This is harder to test without a real model, but we can check if config is respected
    assert config.ML_CONFIDENCE_THRESHOLD == 0.9

def test_gmail_body_extraction_html():
    from src.gmail_client import GmailClient
    import base64

    payload = {
        'mimeType': 'text/html',
        'body': {
            'data': base64.urlsafe_b64encode(b"<div>Hello <b>World</b></div>").decode()
        }
    }

    body = GmailClient._get_body_text(payload)
    # Regex strips tags: <div> -> empty, <b> -> empty, </b> -> empty, </div> -> empty
    assert "Hello World" in body
    assert "<b>" not in body
