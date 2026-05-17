import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from .gmail_client import GmailClient
from .classifier import EmailClassifier

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class MailAgent:
    def __init__(self, gmail_clients: list[GmailClient], classifier: EmailClassifier, max_workers=10):
        self.gmail_clients = gmail_clients
        self.classifier = classifier
        self.max_workers = max_workers

    def process_message(self, gmail_client, msg_meta):
        """Process a single message for a specific client."""
        msg_id = msg_meta['id']
        try:
            message = gmail_client.get_message(msg_id)
            category = self.classifier.classify(message)

            logging.info(f"Message {msg_id} classified as: {category}")

            if category == 'SPAM':
                gmail_client.move_to_trash(msg_id)
                logging.info(f"Moved message {msg_id} to trash (SPAM).")
            elif category == 'SOCIAL':
                gmail_client.apply_labels(msg_id, ['SOCIAL'])
                gmail_client.mark_as_read(msg_id)
                logging.info(f"Labeled message {msg_id} as SOCIAL and marked as read.")
            elif category == 'UPDATES':
                gmail_client.apply_labels(msg_id, ['UPDATES'])
                gmail_client.mark_as_read(msg_id)
                logging.info(f"Labeled message {msg_id} as UPDATES and marked as read.")
            else:
                logging.info(f"Message {msg_id} remains in INBOX.")
            return msg_id, category
        except Exception as e:
            logging.error(f"Error processing message {msg_id}: {e}")
            return msg_id, None

    def run_once(self):
        """Perform a single pass across all configured Gmail accounts."""
        all_tasks = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            for client in self.gmail_clients:
                logging.info(f"Checking for unread messages in an account...")
                try:
                    messages = client.list_unread_messages()
                    if not messages:
                        logging.info("No unread messages found for this account.")
                        continue

                    logging.info(f"Found {len(messages)} unread messages in an account.")
                    for msg in messages:
                        all_tasks.append(executor.submit(self.process_message, client, msg))
                except Exception as e:
                    logging.error(f"Error listing messages for an account: {e}")

            for future in as_completed(all_tasks):
                msg_id, category = future.result()
                if category:
                    logging.info(f"Finished processing message {msg_id}")

    def run_forever(self, interval=60):
        """Run the agent in a loop."""
        logging.info("Starting MailAgent loop for multiple accounts...")
        while True:
            try:
                self.run_once()
            except Exception as e:
                logging.error(f"Error in MailAgent loop: {e}")

            logging.info(f"Sleeping for {interval} seconds...")
            time.sleep(interval)
