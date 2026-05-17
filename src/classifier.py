import re

class EmailClassifier:
    def __init__(self):
        # Refined rule-based classification to reduce false positives
        self.spam_keywords = [
            'lottery prize', 'winner of our lucky draw', 'crypto giveaway',
            'congratulations! you won', 'account suspended - verify now'
        ]
        self.social_keywords = [
            'facebook', 'twitter', 'linkedin', 'instagram'
        ]
        self.update_keywords = [
            'newsletter', 'receipt', 'invoice', 'order', 'shipping'
        ]

    def classify(self, message):
        """
        Classify an email based on its metadata and snippet.
        Returns a suggested label or action.
        """
        snippet = message.get('snippet', '').lower()
        payload = message.get('payload', {})
        headers = payload.get('headers', [])

        subject = ""
        sender = ""
        for header in headers:
            if header['name'].lower() == 'subject':
                subject = header['value'].lower()
            if header['name'].lower() == 'from':
                sender = header['value'].lower()

        text_to_analyze = f"{subject} {snippet}"

        # Check for spam - more specific to avoid false positives
        if any(keyword in text_to_analyze for keyword in self.spam_keywords):
            return 'SPAM'

        # Check for social
        if any(keyword in sender for keyword in self.social_keywords):
            return 'SOCIAL'

        # Check for updates
        if any(keyword in text_to_analyze for keyword in self.update_keywords):
            return 'UPDATES'

        # Default to INBOX if no rules match
        return 'INBOX'
