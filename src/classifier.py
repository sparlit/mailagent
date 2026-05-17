import re
import json
import os
import logging

class EmailClassifier:
    def __init__(self, rules_path='rules.json'):
        self.rules_path = rules_path
        self.rules = self._load_rules()

    def _load_rules(self):
        compiled_rules = {}
        if os.path.exists(self.rules_path):
            try:
                with open(self.rules_path, 'r') as f:
                    raw_rules = json.load(f)
                    for category, config in raw_rules.items():
                        patterns = [re.compile(p, re.I) for p in config.get('patterns', [])]
                        actions = config.get('actions', [])
                        compiled_rules[category] = {
                            'patterns': patterns,
                            'actions': actions
                        }
            except (json.JSONDecodeError, Exception) as e:
                logging.error(f"Error loading rules from {self.rules_path}: {e}")
        return compiled_rules

    def classify(self, message):
        """
        Classify an email based on its metadata and snippet.
        Returns the category name and its associated actions.
        """
        snippet = message.get('snippet', '')
        payload = message.get('payload', {})
        headers = payload.get('headers', [])

        subject = ""
        sender = ""
        for header in headers:
            if header['name'].lower() == 'subject':
                subject = header['value']
            if header['name'].lower() == 'from':
                sender = header['value']

        text_to_analyze = f"{subject} {snippet}"

        for category, config in self.rules.items():
            for pattern in config['patterns']:
                if category == 'SOCIAL':
                    if pattern.search(sender):
                        return category, config['actions']

                if pattern.search(text_to_analyze):
                    return category, config['actions']

        return 'INBOX', []
