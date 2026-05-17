import re

class EmailClassifier:
    def __init__(self):
        # Compiled regex patterns for better performance and more complex matching
        self.spam_patterns = [
            re.compile(r'lottery prize|winner of our lucky draw', re.I),
            re.compile(r'crypto (giveaway|bonus|airdrop)', re.I),
            re.compile(r'congratulations! you won', re.I),
            re.compile(r'account suspended.*verify now', re.I),
            re.compile(r'urgent.*action required.*(bank|account)', re.I),
            re.compile(r'unclaimed (money|funds)', re.I)
        ]
        self.social_patterns = [
            re.compile(r'facebook|twitter|linkedin|instagram|pinterest|tiktok', re.I)
        ]
        self.update_patterns = [
            re.compile(r'newsletter|receipt|invoice|order|shipping|track.*package', re.I),
            re.compile(r'statement|bill.*due|payment (received|confirmed)', re.I)
        ]

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
        for pattern in self.spam_patterns:
            if pattern.search(text_to_analyze):
                return 'SPAM'

        # Check for social (check sender specifically)
        for pattern in self.social_patterns:
            if pattern.search(sender):
                return 'SOCIAL'

        # Check for updates
        for pattern in self.update_patterns:
            if pattern.search(text_to_analyze):
                return 'UPDATES'

        # Default to INBOX
        return 'INBOX'
