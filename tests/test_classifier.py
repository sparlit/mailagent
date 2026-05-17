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
