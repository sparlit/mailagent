import pytest
import os
import sqlite3
from src.database import Database

@pytest.fixture
def db(tmp_path):
    """
    Provide a Database instance backed by a temporary SQLite file for tests.
    
    Returns:
        Database: A Database configured to use a temporary file at `tmp_path / "test.db"`.
    """
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
    """
    Verify that multiple stats can be recorded for the same account/action/category and that get_stats() returns aggregated counts.
    
    Records two "trash"/"SPAM" events and one "label"/"SOCIAL" event for the same email, then asserts the aggregated results include (email, "trash", "SPAM", 2) and (email, "label", "SOCIAL", 1).
    """
    email = "user@example.com"
    db.record_stat(email, "trash", "SPAM")
    db.record_stat(email, "trash", "SPAM")
    db.record_stat(email, "label", "SOCIAL")

    stats = db.get_stats()
    # stats format: (account_email, action, category, count)
    assert (email, "trash", "SPAM", 2) in stats
    assert (email, "label", "SOCIAL", 1) in stats
