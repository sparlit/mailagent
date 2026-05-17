import pytest
import os
import sqlite3
from src.database import Database

@pytest.fixture
def db(tmp_path):
    db_file = tmp_path / "test.db"
    return Database(db_path=str(db_file))

def test_composite_primary_key(db):
    msg_id = "msg1"
    email1 = "user1@example.com"
    email2 = "user2@example.com"

    # Not processed initially
    assert not db.is_processed(msg_id, email1)
    assert not db.is_processed(msg_id, email2)

    # Mark as processed for email1
    db.mark_as_processed(msg_id, email1)
    assert db.is_processed(msg_id, email1)
    assert not db.is_processed(msg_id, email2)

    # Mark as processed for email2
    db.mark_as_processed(msg_id, email2)
    assert db.is_processed(msg_id, email1)
    assert db.is_processed(msg_id, email2)

def test_stats_recording(db):
    email = "user@example.com"
    db.record_stat(email, "trash", "SPAM")
    db.record_stat(email, "trash", "SPAM")
    db.record_stat(email, "label", "SOCIAL")

    stats = db.get_stats()
    # stats format: (account_email, action, category, count)
    assert (email, "trash", "SPAM", 2) in stats
    assert (email, "label", "SOCIAL", 1) in stats


def test_is_processed_returns_false_for_unknown_message(db):
    assert not db.is_processed("nonexistent-msg", "user@example.com")


def test_mark_as_processed_is_idempotent(db):
    # Calling mark_as_processed twice for same (msg_id, email) must not raise
    db.mark_as_processed("msg1", "user@example.com")
    db.mark_as_processed("msg1", "user@example.com")  # INSERT OR IGNORE - no error
    assert db.is_processed("msg1", "user@example.com")


def test_get_stats_returns_empty_for_new_db(db):
    assert db.get_stats() == []


def test_record_stat_multiple_categories_tracked_independently(db):
    email = "multi@example.com"
    db.record_stat(email, "label", "SOCIAL")
    db.record_stat(email, "label", "PROMO")
    db.record_stat(email, "label", "PROMO")

    stats = db.get_stats()
    assert (email, "label", "SOCIAL", 1) in stats
    assert (email, "label", "PROMO", 2) in stats


def test_composite_key_allows_same_message_different_accounts(db):
    # Same message_id processed by two different accounts should both be stored
    db.mark_as_processed("shared-msg", "alice@example.com")
    db.mark_as_processed("shared-msg", "bob@example.com")

    assert db.is_processed("shared-msg", "alice@example.com")
    assert db.is_processed("shared-msg", "bob@example.com")
    # A third account hasn't processed it
    assert not db.is_processed("shared-msg", "carol@example.com")
