import pytest
from unittest.mock import patch, MagicMock
from src.dashboard import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# index() - accounts_count computation (added in this PR)
# ---------------------------------------------------------------------------

def test_index_accounts_count_zero_when_no_stats(client):
    with patch("src.dashboard.db") as mock_db:
        mock_db.get_stats.return_value = []
        response = client.get("/")
    assert response.status_code == 200
    assert b"<strong>0</strong>" in response.data


def test_index_accounts_count_single_account(client):
    stats = [
        ("user@example.com", "trash", "SPAM", 3),
        ("user@example.com", "label", "SOCIAL", 1),
    ]
    with patch("src.dashboard.db") as mock_db:
        mock_db.get_stats.return_value = stats
        response = client.get("/")
    assert response.status_code == 200
    assert b"<strong>1</strong>" in response.data


def test_index_accounts_count_multiple_accounts(client):
    stats = [
        ("alice@example.com", "trash", "SPAM", 2),
        ("bob@example.com", "label", "SOCIAL", 5),
        ("alice@example.com", "mark_read", "NEWS", 1),
    ]
    with patch("src.dashboard.db") as mock_db:
        mock_db.get_stats.return_value = stats
        response = client.get("/")
    assert response.status_code == 200
    assert b"<strong>2</strong>" in response.data


def test_index_deduplicates_accounts(client):
    # Three rows but only two unique accounts; count must be 2, not 3
    stats = [
        ("same@example.com", "trash", "SPAM", 1),
        ("same@example.com", "label", "PROMO", 1),
        ("other@example.com", "star", "VIP", 1),
    ]
    with patch("src.dashboard.db") as mock_db:
        mock_db.get_stats.return_value = stats
        response = client.get("/")
    assert b"<strong>2</strong>" in response.data


# ---------------------------------------------------------------------------
# HTML template: auto-refresh meta tag (added in this PR)
# ---------------------------------------------------------------------------

def test_index_contains_meta_refresh(client):
    with patch("src.dashboard.db") as mock_db:
        mock_db.get_stats.return_value = []
        response = client.get("/")
    assert b'http-equiv="refresh"' in response.data
    assert b'content="30"' in response.data


# ---------------------------------------------------------------------------
# /api/stats endpoint
# ---------------------------------------------------------------------------

def test_api_stats_returns_200(client):
    with patch("src.dashboard.db") as mock_db:
        mock_db.get_stats.return_value = []
        response = client.get("/api/stats")
    assert response.status_code == 200


def test_api_stats_returns_json(client):
    stats = [("user@example.com", "trash", "SPAM", 1)]
    with patch("src.dashboard.db") as mock_db:
        mock_db.get_stats.return_value = stats
        response = client.get("/api/stats")
    assert response.content_type.startswith("application/json")
    data = response.get_json()
    assert isinstance(data, list)
    assert len(data) == 1


def test_api_stats_empty(client):
    with patch("src.dashboard.db") as mock_db:
        mock_db.get_stats.return_value = []
        response = client.get("/api/stats")
    assert response.get_json() == []


# ---------------------------------------------------------------------------
# Stat rows rendered in the HTML table
# ---------------------------------------------------------------------------

def test_index_renders_stat_rows(client):
    stats = [("agent@example.com", "archive", "PROMO", 7)]
    with patch("src.dashboard.db") as mock_db:
        mock_db.get_stats.return_value = stats
        response = client.get("/")
    assert b"agent@example.com" in response.data
    assert b"archive" in response.data
    assert b"PROMO" in response.data
    assert b"7" in response.data