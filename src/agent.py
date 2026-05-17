import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from .gmail_client import GmailClient
from .classifier import EmailClassifier

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class MailAgent:
    def __init__(self, gmail_client: GmailClient, classifier: EmailClassifier, max_workers=5):
        self.gmail = gmail_client
        self.classifier = classifier
        self.max_workers = max_workers

    def process_message(self, msg_meta):
        """Process a single message."""
        msg_id = msg_meta['id']
        try:
            message = self.gmail.get_message(msg_id)
            category = self.classifier.classify(message)

            logging.info(f"Message {msg_id} classified as: {category}")

            if category == 'SPAM':
                self.gmail.move_to_trash(msg_id)
                logging.info(f"Moved message {msg_id} to trash (SPAM).")
            elif category == 'SOCIAL':
                self.gmail.apply_labels(msg_id, ['SOCIAL'])
                self.gmail.mark_as_read(msg_id)
                logging.info(f"Labeled message {msg_id} as SOCIAL and marked as read.")
            elif category == 'UPDATES':
                self.gmail.apply_labels(msg_id, ['UPDATES'])
                self.gmail.mark_as_read(msg_id)
                logging.info(f"Labeled message {msg_id} as UPDATES and marked as read.")
            else:
                logging.info(f"Message {msg_id} remains in INBOX.")
            return msg_id, category
        except Exception as e:
            logging.error(f"Error processing message {msg_id}: {e}")
            return msg_id, None

    def run_once(self):
        """Perform a single pass of checking and organizing emails using parallel processing."""
        logging.info("Checking for unread messages...")
        messages = self.gmail.list_unread_messages()

        if not messages:
            logging.info("No unread messages found.")
            return

        logging.info(f"Found {len(messages)} unread messages. Processing with {self.max_workers} workers.")

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_msg = {executor.submit(self.process_message, msg): msg for msg in messages}
            for future in as_completed(future_to_msg):
                msg_id, category = future.result()
                if category:
                    logging.info(f"Finished processing message {msg_id}")

    def run_forever(self, interval=60):
        """Run the agent in a loop."""
        logging.info("Starting MailAgent loop...")
        while True:
            try:
                self.run_once()
            except Exception as e:
                logging.error(f"Error in MailAgent loop: {e}")

            logging.info(f"Sleeping for {interval} seconds...")
            time.sleep(interval)
