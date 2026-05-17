import re
import json
import os
import logging

class EmailClassifier:
    def __init__(self, rules_path='rules.json'):
        """
        Initialize an EmailClassifier and load its classification rules.
        
        Parameters:
            rules_path (str): Path to the JSON file containing classification rules (default: 'rules.json'). The rules are immediately loaded and stored on the instance as `self.rules`.
        """
        self.rules_path = rules_path
        self.rules = self._load_rules()

    def _load_rules(self):
        """
        Load classification rules from the configured JSON file and return them in a compiled form.
        
        Each returned key is a category name mapped to a dict with:
        - `patterns`: list of case-insensitive compiled regular expressions for general matching,
        - `header_rules`: list of dicts with `name` (lowercased header name) and `pattern` (case-insensitive compiled regex),
        - `actions`: list of actions from the rule config.
        
        If the rules file does not exist, an empty dict is returned. On JSON parse errors or other exceptions the function logs an error and returns whatever rules were successfully compiled before the failure.
        
        Returns:
            dict: Compiled rules keyed by category.
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
        Determine the mailbox category and associated actions for a given email message.
        
        Parameters:
            message (dict): Email message mapping expected to include:
                - 'snippet' (str, optional): short text excerpt of the message.
                - 'payload' (dict, optional): message payload containing:
                    - 'headers' (list): list of header dicts each with 'name' and 'value'.
                Header names are treated case-insensitively when matching.
        
        Returns:
            tuple: (category, actions)
                category (str): the matched category name; returns 'INBOX' if no rule matches.
                actions (list): list of actions configured for the matched category; empty list if none or no match.
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

    def reload_rules(self):
        """
        Reload the classifier rules from the configured JSON file and update the instance's rules.
        
        This replaces the classifier's in-memory rules with the latest compiled rules read from the configured `rules_path` and logs an informational message on success.
        """
        self.rules = self._load_rules()
        logging.info(f"Rules reloaded from {self.rules_path}")
