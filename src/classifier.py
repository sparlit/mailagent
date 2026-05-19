import re
import json
import os
import logging

__all__ = ['EmailClassifier']

class EmailClassifier:
    def __init__(self, rules_path='rules.json'):
        self.rules_path = rules_path
        self.rules = self._load_rules()

    def _load_rules(self):
        """
        Load and compile email classification rules from the configured JSON file.
        
        If the file at self.rules_path exists, parse it as JSON and compile each category's
        pattern strings into case-insensitive regular expressions and each header rule into a
        dict with a lowercased header name and a case-insensitive compiled pattern. On JSON
        parsing or other errors, log the error and return whatever rules were compiled up to
        that point (or an empty dict if none).
        
        Returns:
            dict: Mapping of category name to a dict with keys:
                - 'patterns' (list): compiled regular expression objects for general matching.
                - 'header_rules' (list): dicts with keys:
                    - 'name' (str): lowercased header name to match (e.g., 'from', 'subject').
                    - 'pattern' (re.Pattern): compiled regex for the header value.
                - 'actions' (list): actions associated with the category from the JSON.
        """
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
        """
        Reloads and recompiles classification rules from the configured rules file into the instance.
        
        Replaces the instance's `self.rules` with the freshly loaded and compiled rules from `self.rules_path`.
        """
        logging.info(f"Reloading rules from {self.rules_path}")
        self.rules = self._load_rules()

    def classify(self, message):
        """
        Determine the classification category and associated actions for an email message using the classifier's compiled rules.
        
        Header-based rules are evaluated first (highest priority). If no header rule matches for a category, general regex patterns are tested against the sender and the combined subject+snippet text. Matching stops at the first category that matches.
        
        Parameters:
            message (dict): Email data expected to contain optional keys:
                - 'snippet' (str): short message preview.
                - 'payload' (dict): may contain 'headers' (list of dicts with 'name' and 'value').
        
        Returns:
            tuple: `(category, actions)` where `category` is the matched category name (str) and `actions` is the list of actions for that category. Returns `('INBOX', [])` if no rules match.
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
