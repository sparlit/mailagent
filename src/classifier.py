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
                        header_rules = []
                        for hr in config.get('header_rules', []):
                            header_rules.append({
                                'name': hr['name'].lower(),
                                'pattern': re.compile(hr['pattern'], re.I)
                            })

                        compiled_rules[category] = {
                            'patterns': patterns,
                            'header_rules': header_rules,
                            'actions': config.get('actions', [])
                        }
            except (json.JSONDecodeError, Exception) as e:
                logging.error(f"Error loading rules from {self.rules_path}: {e}")
        return compiled_rules

    def reload_rules(self):
        """Reload and recompile rules from rules.json."""
        logging.info(f"Reloading rules from {self.rules_path}")
        self.rules = self._load_rules()

    def classify(self, message):
        """
        Classify an email based on its metadata and snippet.
        """
        snippet = message.get('snippet', '')
        payload = message.get('payload', {})
        headers = payload.get('headers', [])

        header_dict = {h['name'].lower(): h['value'] for h in headers}
        subject = header_dict.get('subject', '')
        sender = header_dict.get('from', '')

        text_to_analyze = f"{subject} {snippet}"

        for category, config in self.rules.items():
            # 1. Check Header Rules (High Priority)
            for hr in config.get('header_rules', []):
                val = header_dict.get(hr['name'])
                if val and hr['pattern'].search(val):
                    return category, config['actions']

            # 2. Check General Patterns
            for pattern in config['patterns']:
                if pattern.search(sender) or pattern.search(text_to_analyze):
                    return category, config['actions']

        return 'INBOX', []
