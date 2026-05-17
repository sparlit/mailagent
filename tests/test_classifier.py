import pytest
import os
import json
from src.classifier import EmailClassifier

@pytest.fixture
def classifier(tmp_path):
    rules = {
        "TEST": {
            "patterns": ["test pattern"],
            "header_rules": [{"name": "X-Test", "pattern": "match"}],
            "actions": ["label"]
        }
    }
    rules_file = tmp_path / "rules.json"
    rules_file.write_text(json.dumps(rules))
    return EmailClassifier(rules_path=str(rules_file))

def test_classify_by_pattern(classifier):
    message = {
        "snippet": "this is a test pattern",
        "payload": {"headers": []}
    }
    category, actions = classifier.classify(message)
    assert category == "TEST"
    assert actions == ["label"]

def test_classify_by_header(classifier):
    message = {
        "snippet": "no match here",
        "payload": {
            "headers": [{"name": "X-Test", "value": "match"}]
        }
    }
    category, actions = classifier.classify(message)
    assert category == "TEST"
    assert actions == ["label"]

def test_classify_by_sender(classifier):
    # Sender should also be checked against patterns
    message = {
        "snippet": "no match in snippet",
        "payload": {
            "headers": [{"name": "From", "value": "test pattern <sender@example.com>"}]
        }
    }
    category, actions = classifier.classify(message)
    assert category == "TEST"

def test_reload_rules(classifier, tmp_path):
    # Initial classification
    msg = {"snippet": "new rules", "payload": {"headers": []}}
    cat, _ = classifier.classify(msg)
    assert cat == "INBOX"

    # Update rules
    rules = {
        "NEW": {
            "patterns": ["new rules"],
            "actions": ["trash"]
        }
    }
    rules_file = tmp_path / "rules.json"
    rules_file.write_text(json.dumps(rules))

    classifier.reload_rules()
    cat, actions = classifier.classify(msg)
    assert cat == "NEW"
    assert actions == ["trash"]


def test_no_match_returns_inbox(classifier):
    message = {
        "snippet": "completely unrelated content",
        "payload": {"headers": [{"name": "From", "value": "nobody@example.com"}]}
    }
    category, actions = classifier.classify(message)
    assert category == "INBOX"
    assert actions == []


def test_pattern_matching_is_case_insensitive(classifier):
    # Rules are compiled with re.I; pattern "test pattern" should match "TEST PATTERN"
    message = {
        "snippet": "TEST PATTERN in uppercase",
        "payload": {"headers": []}
    }
    category, actions = classifier.classify(message)
    assert category == "TEST"
    assert actions == ["label"]


def test_classify_missing_snippet(classifier):
    # message without 'snippet' key should not raise
    message = {
        "payload": {"headers": [{"name": "X-Test", "value": "match"}]}
    }
    category, actions = classifier.classify(message)
    assert category == "TEST"
    assert actions == ["label"]


def test_classify_missing_payload(classifier):
    # message without 'payload' key falls back gracefully
    message = {"snippet": "test pattern here"}
    category, actions = classifier.classify(message)
    assert category == "TEST"


def test_reload_rules_clears_old_rules(classifier, tmp_path):
    # Verify that after reloading with empty rules, old patterns no longer match
    rules_file = tmp_path / "rules.json"
    rules_file.write_text(json.dumps({}))
    classifier.reload_rules()

    message = {
        "snippet": "this is a test pattern",
        "payload": {"headers": []}
    }
    category, actions = classifier.classify(message)
    assert category == "INBOX"
    assert actions == []


def test_classify_header_rule_not_matched_falls_through_to_pattern(tmp_path):
    # Header rule present but not matching; pattern match should still classify
    rules = {
        "CATEGORY": {
            "patterns": ["keyword"],
            "header_rules": [{"name": "X-Custom", "pattern": "specific-value"}],
            "actions": ["label"]
        }
    }
    rules_file = tmp_path / "rules.json"
    rules_file.write_text(json.dumps(rules))
    clf = EmailClassifier(rules_path=str(rules_file))

    message = {
        "snippet": "contains keyword",
        "payload": {
            "headers": [{"name": "X-Custom", "value": "other-value"}]
        }
    }
    category, actions = clf.classify(message)
    assert category == "CATEGORY"
    assert actions == ["label"]


def test_classify_sender_matched_by_pattern(tmp_path):
    # Sender field is now checked against patterns directly (changed from SOCIAL-only logic)
    rules = {
        "PROMO": {
            "patterns": ["noreply@store\\.com"],
            "actions": ["trash"]
        }
    }
    rules_file = tmp_path / "rules.json"
    rules_file.write_text(json.dumps(rules))
    clf = EmailClassifier(rules_path=str(rules_file))

    message = {
        "snippet": "Your order has shipped",
        "payload": {
            "headers": [{"name": "From", "value": "noreply@store.com"}]
        }
    }
    category, actions = clf.classify(message)
    assert category == "PROMO"
    assert actions == ["trash"]
