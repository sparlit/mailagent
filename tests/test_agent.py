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


# ---------------------------------------------------------------------------
# Tests for PR changes: dry_run, new actions, is_processed with email, etc.
# ---------------------------------------------------------------------------

def _make_agent(db, dry_run=False):
    """Helper that builds a MailAgent with a mock client and classifier."""
    client = MagicMock()
    client.email_address = "agent@example.com"
    mock_clf = MagicMock()
    mock_clf.classify.return_value = ("SPAM", ["trash"])
    return MailAgent([client], mock_clf, db, dry_run=dry_run), client, mock_clf


# --- dry_run: client methods must not be called ---

def test_dry_run_skips_trash(db):
    agent, client, _ = _make_agent(db, dry_run=True)
    agent.execute_actions(client, "m1", "SPAM", ["trash"])
    client.move_to_trash.assert_not_called()


def test_dry_run_skips_label(db):
    agent, client, _ = _make_agent(db, dry_run=True)
    agent.execute_actions(client, "m1", "SOCIAL", ["label"])
    client.apply_labels.assert_not_called()


def test_dry_run_skips_mark_read(db):
    agent, client, _ = _make_agent(db, dry_run=True)
    agent.execute_actions(client, "m1", "NEWS", ["mark_read"])
    client.mark_as_read.assert_not_called()


def test_dry_run_skips_archive(db):
    agent, client, _ = _make_agent(db, dry_run=True)
    agent.execute_actions(client, "m1", "PROMO", ["archive"])
    client.archive.assert_not_called()


def test_dry_run_skips_star(db):
    agent, client, _ = _make_agent(db, dry_run=True)
    agent.execute_actions(client, "m1", "VIP", ["star"])
    client.star.assert_not_called()


def test_dry_run_still_records_stats(db):
    """Stats must be recorded even in dry_run mode."""
    agent, client, _ = _make_agent(db, dry_run=True)
    agent.execute_actions(client, "m1", "SPAM", ["trash"])
    stats = db.get_stats()
    assert any(s[1] == "trash" and s[2] == "SPAM" for s in stats)


# --- new actions: archive and star ---

def test_execute_archive_action(db):
    agent, client, _ = _make_agent(db, dry_run=False)
    agent.execute_actions(client, "m1", "PROMO", ["archive"])
    client.archive.assert_called_once_with("m1")


def test_execute_star_action(db):
    agent, client, _ = _make_agent(db, dry_run=False)
    agent.execute_actions(client, "m1", "VIP", ["star"])
    client.star.assert_called_once_with("m1")


def test_execute_archive_records_stat(db):
    agent, client, _ = _make_agent(db, dry_run=False)
    agent.execute_actions(client, "m1", "PROMO", ["archive"])
    stats = db.get_stats()
    assert (client.email_address, "archive", "PROMO", 1) in stats


def test_execute_star_records_stat(db):
    agent, client, _ = _make_agent(db, dry_run=False)
    agent.execute_actions(client, "m1", "VIP", ["star"])
    stats = db.get_stats()
    assert (client.email_address, "star", "VIP", 1) in stats


def test_execute_unstar_action(db):
    agent, client, _ = _make_agent(db, dry_run=False)
    agent.execute_actions(client, "m1", "VIP", ["unstar"])
    client.unstar.assert_called_once_with("m1")


def test_execute_mark_important_action(db):
    agent, client, _ = _make_agent(db, dry_run=False)
    agent.execute_actions(client, "m1", "VIP", ["mark_important"])
    client.mark_important.assert_called_once_with("m1")


# --- process_message: is_processed now requires account_email ---

def test_process_message_passes_email_to_is_processed(db):
    mock_client = MagicMock()
    mock_client.email_address = "multi@example.com"
    mock_client.list_unread_messages.return_value = [{"id": "msgX"}]
    mock_client.get_message.return_value = {
        "snippet": "test",
        "payload": {"headers": []}
    }
    mock_clf = MagicMock()
    mock_clf.classify.return_value = ("INBOX", [])

    agent = MailAgent([mock_client], mock_clf, db)
    agent.process_message(mock_client, {"id": "msgX"})

    # After processing, it must be recorded under the correct email
    assert db.is_processed("msgX", "multi@example.com")


def test_process_message_skips_already_processed_for_same_account(db):
    mock_client = MagicMock()
    mock_client.email_address = "owner@example.com"

    db.mark_as_processed("dup-msg", "owner@example.com")

    mock_clf = MagicMock()
    agent = MailAgent([mock_client], mock_clf, db)
    msg_id, category = agent.process_message(mock_client, {"id": "dup-msg"})

    assert msg_id == "dup-msg"
    assert category is None
    mock_client.get_message.assert_not_called()


def test_same_message_processed_by_two_accounts(db):
    """Same message_id from two different accounts should both be processed."""
    client_a = MagicMock()
    client_a.email_address = "a@example.com"
    client_b = MagicMock()
    client_b.email_address = "b@example.com"

    for client in (client_a, client_b):
        client.get_message.return_value = {
            "snippet": "hi",
            "payload": {"headers": []}
        }

    mock_clf = MagicMock()
    mock_clf.classify.return_value = ("INBOX", [])

    agent = MailAgent([client_a, client_b], mock_clf, db)
    agent.process_message(client_a, {"id": "shared"})
    agent.process_message(client_b, {"id": "shared"})

    assert db.is_processed("shared", "a@example.com")
    assert db.is_processed("shared", "b@example.com")


# --- run_forever: reload_rules called each iteration ---

def test_run_forever_calls_reload_rules(db):
    mock_client = MagicMock()
    mock_client.email_address = "loop@example.com"
    mock_clf = MagicMock()

    agent = MailAgent([mock_client], mock_clf, db)

    call_count = {"n": 0}

    def stopping_run_once():
        call_count["n"] += 1
        if call_count["n"] >= 2:
            raise KeyboardInterrupt

    agent.run_once = stopping_run_once

    import time as _time
    with patch.object(_time, 'sleep', return_value=None):
        try:
            agent.run_forever(interval=0, start_dashboard=False)
        except KeyboardInterrupt:
            pass

    # reload_rules should have been called once per loop iteration
    assert mock_clf.reload_rules.call_count >= 2
