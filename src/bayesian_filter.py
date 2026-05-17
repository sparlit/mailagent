import math
import re
import json
import os

class BayesianFilter:
    def __init__(self, model_path='bayesian_model.json'):
        self.model_path = model_path
        self.spam_counts = {}
        self.ham_counts = {}
        self.total_spam = 0
        self.total_ham = 0
        self.load_model()

    def tokenize(self, text):
        return re.findall(r'[a-z0-9]+', text.lower())

    def load_model(self):
        if self.model_path == ':memory:':
            return
        if os.path.exists(self.model_path):
            with open(self.model_path, 'r') as f:
                data = json.load(f)
                self.spam_counts = data.get('spam_counts', {})
                self.ham_counts = data.get('ham_counts', {})
                self.total_spam = data.get('total_spam', 0)
                self.total_ham = data.get('total_ham', 0)

    def save_model(self):
        if self.model_path == ':memory:':
            return
        with open(self.model_path, 'w') as f:
            json.dump({
                'spam_counts': self.spam_counts,
                'ham_counts': self.ham_counts,
                'total_spam': self.total_spam,
                'total_ham': self.total_ham
            }, f)

    def train(self, text, is_spam=True):
        tokens = self.tokenize(text)
        if is_spam:
            self.total_spam += 1
            for token in set(tokens):
                self.spam_counts[token] = self.spam_counts.get(token, 0) + 1
        else:
            self.total_ham += 1
            for token in set(tokens):
                self.ham_counts[token] = self.ham_counts.get(token, 0) + 1

    def predict(self, text):
        if self.total_spam == 0 or self.total_ham == 0:
            return 0.5  # Neutral if not trained

        tokens = self.tokenize(text)
        spam_prob = math.log(self.total_spam / (self.total_spam + self.total_ham))
        ham_prob = math.log(self.total_ham / (self.total_spam + self.total_ham))

        for token in tokens:
            # Using Laplace smoothing
            s_count = self.spam_counts.get(token, 0)
            h_count = self.ham_counts.get(token, 0)

            p_token_spam = (s_count + 1) / (self.total_spam + 2)
            p_token_ham = (h_count + 1) / (self.total_ham + 2)

            spam_prob += math.log(p_token_spam)
            ham_prob += math.log(p_token_ham)

        # Convert back to probability
        try:
            max_p = max(spam_prob, ham_prob)
            prob = math.exp(spam_prob - max_p) / (math.exp(spam_prob - max_p) + math.exp(ham_prob - max_p))
            return prob
        except OverflowError:
            return 1.0 if spam_prob > ham_prob else 0.0
