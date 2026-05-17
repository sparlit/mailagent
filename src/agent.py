import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from .gmail_client import GmailClient
from .classifier import EmailClassifier
from .database import Database

class MailAgent:
    def __init__(self, gmail_clients: list[GmailClient], classifier: EmailClassifier, db: Database, max_workers=10):
        self.gmail_clients = gmail_clients
        self.classifier = classifier
        self.db = db
        self.max_workers = max_workers

    def execute_actions(self, client, msg_id, category, actions):
        """Execute a list of actions for a message."""
        for action in actions:
            if action == 'trash':
                client.move_to_trash(msg_id)
                logging.info(f"Action 'trash' executed for {msg_id}")
            elif action == 'label':
                client.apply_labels(msg_id, [category])
                logging.info(f"Action 'label' ({category}) executed for {msg_id}")
            elif action == 'mark_read':
                client.mark_as_read(msg_id)
                logging.info(f"Action 'mark_read' executed for {msg_id}")

    def process_message(self, gmail_client, msg_meta):
        """Process a single message for a specific client."""
        msg_id = msg_meta['id']

        if self.db.is_processed(msg_id):
            logging.info(f"Message {msg_id} already processed. Skipping.")
            return msg_id, None

        try:
            message = gmail_client.get_message(msg_id)
            category, actions = self.classifier.classify(message)

            logging.info(f"Message {msg_id} classified as: {category} with actions: {actions}")

            self.execute_actions(gmail_client, msg_id, category, actions)

            self.db.mark_as_processed(msg_id)
            return msg_id, category
        except Exception as e:
            logging.error(f"Error processing message {msg_id}: {e}")
            return msg_id, None

    def run_once(self):
        """Perform a single pass across all configured Gmail accounts."""
        all_tasks = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            for client in self.gmail_clients:
                logging.info("Checking for unread messages in an account...")
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
        logging.info("Starting MailAgent loop with persistence and dynamic actions...")
        while True:
            try:
                self.run_once()
            except Exception as e:
                logging.error(f"Error in MailAgent loop: {e}")

            logging.info(f"Sleeping for {interval} seconds...")
            time.sleep(interval)
