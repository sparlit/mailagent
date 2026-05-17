import re
import json
import os
import logging
from .bayesian_filter import BayesianFilter

class EmailClassifier:
    def __init__(self, rules_path='rules.json', bayesian_model_path='bayesian_model.json'):
        self.rules_path = rules_path
        self.rules = self._load_rules()
        self.bayesian = BayesianFilter(model_path=bayesian_model_path)

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

    def classify(self, message):
        """
        Classify an email based on its metadata, snippet, and full body.
        """
        snippet = message.get('snippet', '')
        full_body = message.get('full_body', '')
        payload = message.get('payload', {})
        headers = payload.get('headers', [])

        header_dict = {h['name'].lower(): h['value'] for h in headers}
        subject = header_dict.get('subject', '')
        sender = header_dict.get('from', '')

        # Analyze subject, snippet, and full body
        text_to_analyze = f"{subject} {snippet} {full_body}"

        # 1. Check Header Rules (High Priority)
        for category, config in self.rules.items():
            for hr in config.get('header_rules', []):
                val = header_dict.get(hr['name'])
                if val and hr['pattern'].search(val):
                    return category, config['actions']

        # 2. Check General Patterns
        for category, config in self.rules.items():
            for pattern in config['patterns']:
                if category == 'SOCIAL':
                    if pattern.search(sender):
                        return category, config['actions']

                if pattern.search(text_to_analyze):
                    return category, config['actions']

        # 3. Bayesian Classification for Spam (Secondary)
        spam_probability = self.bayesian.predict(text_to_analyze)
        if spam_probability > 0.9:
            logging.info(f"Bayesian filter triggered: Spam probability {spam_probability:.2f}")
            return 'SPAM', self.rules.get('SPAM', {}).get('actions', ['trash'])

        return 'INBOX', []
