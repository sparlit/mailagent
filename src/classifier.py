import re
import json
import os
import logging
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from .gmail_client import GmailClient
from . import config

__all__ = ['EmailClassifier']

from typing import Dict, Any, List, Tuple, Optional

class EmailClassifier:
    def __init__(self, rules_path: str = 'rules.json') -> None:
        self.rules_path = rules_path
        self.rules = self._load_rules()
        self.ml_model = self._train_fallback_model()

    def _load_rules(self) -> Dict[str, Any]:
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
                    for category, config_data in raw_rules.items():
                        patterns = [re.compile(p, re.I) for p in config_data.get('patterns', [])]
                        header_rules = []
                        for hr in config_data.get('header_rules', []):
                            header_rules.append({
                                'name': hr['name'].lower(),
                                'pattern': re.compile(hr['pattern'], re.I)
                            })

                        compiled_rules[category] = {
                            'patterns': patterns,
                            'header_rules': header_rules,
                            'actions': config_data.get('actions', [])
                        }
            except (json.JSONDecodeError, Exception) as e:
                logging.error(f"Error loading rules from {self.rules_path}: {e}")
        return compiled_rules

    def _train_fallback_model(self) -> Optional[Pipeline]:
        """
        Train a simple Naive Bayes model based on the patterns in rules.json.
        This serves as a fallback when exact regex matching fails.
        """
        training_data = []
        labels = []

        if not os.path.exists(self.rules_path):
            return None

        try:
            with open(self.rules_path, 'r') as f:
                raw_rules = json.load(f)
                for category, config_data in raw_rules.items():
                    for pattern in config_data.get('patterns', []):
                        # We use the raw pattern string (simplified) for training
                        clean_pattern = pattern.replace('(', '').replace(')', '').replace('|', ' ').replace('.*', ' ')
                        training_data.append(clean_pattern)
                        labels.append(category)
        except Exception as e:
            logging.error(f"Error reading rules for ML training: {e}")
            return None

        if not training_data or len(set(labels)) < 2:
            return None

        pipeline = Pipeline([
            ('vectorizer', CountVectorizer()),
            ('clf', MultinomialNB())
        ])

        try:
            pipeline.fit(training_data, labels)
            logging.info("Fallback ML model trained successfully.")
            return pipeline
        except Exception as e:
            logging.error(f"Failed to train fallback ML model: {e}")
            return None

    def reload_rules(self) -> None:
        """
        Reloads and recompiles classification rules from the configured rules file into the instance.
        
        Replaces the instance's `self.rules` with the freshly loaded and compiled rules from `self.rules_path`.
        """
        logging.info(f"Reloading rules from {self.rules_path}")
        self.rules = self._load_rules()
        self.ml_model = self._train_fallback_model()

    def classify(self, message: Dict[str, Any]) -> Tuple[str, List[str]]:
        """
        Determine the classification category and associated actions for an email message using the classifier's compiled rules.
        
        Header-based rules are evaluated first (highest priority). If no header rule matches for a category, general regex patterns are tested against the sender and the combined subject, snippet, and body text. Matching stops at the first category that matches.
        
        Parameters:
            message (dict): Email data expected to contain optional keys:
                - 'snippet' (str): short message preview.
                - 'body_text' (str): full message body (optional).
                - 'payload' (dict): may contain 'headers' (list of dicts with 'name' and 'value') and 'parts'.
        
        Returns:
            tuple: `(category, actions)` where `category` is the matched category name (str) and `actions` is the list of actions for that category. Returns `('INBOX', [])` if no rules match.
        """
        snippet = message.get('snippet', '')
        payload = message.get('payload', {})
        headers = payload.get('headers', [])

        header_dict = {h['name'].lower(): h['value'] for h in headers}
        subject = header_dict.get('subject', '')
        sender = header_dict.get('from', '')

        # Use body_text if provided by the agent, else extract it
        body = message.get('body_text')
        if not body:
            body = GmailClient._get_body_text(payload)

        text_to_analyze = f"{subject} {snippet} {body}".strip()

        for category, config_data in self.rules.items():
            # 1. Check Header Rules (High Priority)
            for hr in config_data.get('header_rules', []):
                val = header_dict.get(hr['name'])
                if val and hr['pattern'].search(val):
                    return category, config_data['actions']

            # 2. Check General Patterns
            for pattern in config_data['patterns']:
                if pattern.search(sender) or pattern.search(text_to_analyze):
                    return category, config_data['actions']

        # 3. ML Fallback
        if self.ml_model:
            try:
                # Get probabilities
                probs = self.ml_model.predict_proba([text_to_analyze])[0]
                max_prob = max(probs)
                if max_prob > config.ML_CONFIDENCE_THRESHOLD:  # Confidence threshold
                    category = self.ml_model.classes_[probs.argmax()]
                    logging.info(f"ML Fallback: Classified message as {category} with confidence {max_prob:.2f}")
                    return category, self.rules[category]['actions']
            except Exception as e:
                logging.error(f"ML Fallback failed: {e}")

        return 'INBOX', []
