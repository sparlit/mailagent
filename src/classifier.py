import re
import json
import os
import logging

class EmailClassifier:
    def __init__(self, rules_path='rules.json'):
        """
        Initialize an EmailClassifier and load classification rules from a JSON file.
        
        Parameters:
            rules_path (str): Filesystem path to a JSON rules file (default: 'rules.json'). The file is parsed and its rule definitions are compiled into the instance's `rules`.
        """
        self.rules_path = rules_path
        self.rules = self._load_rules()

    def _load_rules(self):
        """
        Load classification rules from the configured JSON file and compile them for use.
        
        Parses the JSON at self.rules_path (if it exists) and returns a mapping of category names to prepared rule configs. Each config contains:
        - `patterns`: list of case-insensitive compiled regex objects from the category's `patterns`.
        - `header_rules`: list of dicts with `name` (lowercased header name) and a case-insensitive compiled regex `pattern`.
        - `actions`: the category's `actions` list (defaults to empty list).
        
        If the rules file does not exist, or if parsing/processing fails, an empty dict (or whatever was successfully compiled before the error) is returned and an error is logged.
        
        Returns:
            dict: Mapping of category -> {'patterns': [re.Pattern, ...], 'header_rules': [{'name': str, 'pattern': re.Pattern}, ...], 'actions': list}
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

    def classify(self, message):
        """
        Determine an email's category and associated actions using configured header rules and regex patterns.
        
        The classifier examines headers (case-insensitive by name), the message subject, and a message snippet. Header-specific rules are evaluated first and take precedence; if a header rule matches its header value the corresponding category and actions are returned. For general patterns, patterns in the "SOCIAL" category are matched against the sender (the `From` header); all other patterns are matched against the concatenation of subject and snippet. The first matching rule wins.
        
        Parameters:
            message (dict): Email representation with optional keys:
                - 'snippet' (str): short text excerpt of the message.
                - 'payload' (dict): message payload containing 'headers' (list of dicts with 'name' and 'value').
        
        Returns:
            tuple: A pair (category, actions) where `category` is the matched category string and `actions` is the list of actions from that category's config. If no rules match, returns ('INBOX', []).
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
                if category == 'SOCIAL':
                    if pattern.search(sender):
                        return category, config['actions']

                if pattern.search(text_to_analyze):
                    return category, config['actions']

        return 'INBOX', []
