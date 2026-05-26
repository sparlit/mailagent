import pytest
import os
import re
from src.config import ML_CONFIDENCE_THRESHOLD, MAX_MESSAGES_PER_CYCLE
from src.gmail_client import GmailClient
from src.database import Database

def test_config_defaults():
    assert ML_CONFIDENCE_THRESHOLD == 0.5
    assert MAX_MESSAGES_PER_CYCLE == 50

def test_html_tag_stripping():
    html = "<html><body><h1>Hello</h1><p>World!</p></body></html>"
    # Gmail uses base64url encoding for data
    import base64
    encoded_html = base64.urlsafe_b64encode(html.encode('utf-8')).decode('utf-8')

    payload = {
        'parts': [
            {
                'mimeType': 'text/html',
                'body': {'data': encoded_html}
            }
        ]
    }

    body = GmailClient._get_body_text(payload)
    assert "Hello" in body
    assert "World!" in body
    assert "<h1>" not in body
    assert "<html>" not in body

def test_activity_logging(tmp_path):
    db_file = tmp_path / "test_activity.db"
    db = Database(str(db_file))

    db.log_activity("test@example.com", "msg123", "label", "WORK")
    recent = db.get_recent_activity(limit=5)

    assert len(recent) == 1
    assert recent[0][0] == "test@example.com"
    assert recent[0][1] == "msg123"
    assert recent[0][2] == "label"
    assert recent[0][3] == "WORK"

def test_max_messages_limit():
    from src.agent import MailAgent
    from src.classifier import EmailClassifier
    from src.gmail_client import MockGmailClient
    import src.config as config

    # Mock config
    original_limit = config.MAX_MESSAGES_PER_CYCLE
    config.MAX_MESSAGES_PER_CYCLE = 2

    try:
        mock_client = MockGmailClient()
        # Mock list_unread_messages to return 5 messages
        mock_client.list_unread_messages = lambda: [{'id': f'msg{i}'} for i in range(5)]

        agent = MailAgent([mock_client], None, None, max_workers=1)

        # We need to mock process_message to avoid failures since classifier/db are None
        processed_ids = []
        def mock_process(client, msg_meta):
            processed_ids.append(msg_meta['id'])
            return msg_meta['id'], "CATEGORY"

        agent.process_message = mock_process

        agent.run_once()

        assert len(processed_ids) == 2
    finally:
        config.MAX_MESSAGES_PER_CYCLE = original_limit
