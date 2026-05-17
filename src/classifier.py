import re
import json
import os

class EmailClassifier:
    def __init__(self, rules_path='rules.json'):
        self.rules_path = rules_path
        self.patterns = self._load_rules()

    def _load_rules(self):
        patterns = {
            'SPAM': [],
            'SOCIAL': [],
            'UPDATES': []
        }
        if os.path.exists(self.rules_path):
            try:
                with open(self.rules_path, 'r') as f:
                    rules = json.load(f)
                    for category, regex_list in rules.items():
                        patterns[category] = [re.compile(r, re.I) for r in regex_list]
            except (json.JSONDecodeError, Exception) as e:
                print(f"Error loading rules from {self.rules_path}: {e}")
        return patterns

    def classify(self, message):
        """
        Classify an email based on its metadata and snippet.
        Returns a suggested label or action.
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

        # Check for spam
        for pattern in self.patterns.get('SPAM', []):
            if pattern.search(text_to_analyze):
                return 'SPAM'

        # Check for social (check sender specifically)
        for pattern in self.patterns.get('SOCIAL', []):
            if pattern.search(sender):
                return 'SOCIAL'

        # Check for updates
        for pattern in self.patterns.get('UPDATES', []):
            if pattern.search(text_to_analyze):
                return 'UPDATES'

        # Default to INBOX
        return 'INBOX'
