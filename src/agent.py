import time
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from .gmail_client import GmailClient
from .classifier import EmailClassifier
from .database import Database
from .dashboard import run_dashboard

class MailAgent:
    def __init__(self, gmail_clients: list[GmailClient], classifier: EmailClassifier, db: Database, max_workers=10, dry_run=False):
        self.gmail_clients = gmail_clients
        self.classifier = classifier
        self.db = db
        self.max_workers = max_workers
        self.dry_run = dry_run

    def execute_actions(self, client, msg_id, category, actions):
        """Execute a list of actions for a message and record stats."""
        for action in actions:
            try:
                if self.dry_run:
                    logging.info(f"[DRY RUN] Would execute action '{action}' for message {msg_id}")
                else:
                    if action == 'trash':
                        client.move_to_trash(msg_id)
                        logging.info(f"Action 'trash' executed for {msg_id}")
                    elif action == 'label':
                        client.apply_labels(msg_id, [category])
                        logging.info(f"Action 'label' ({category}) executed for {msg_id}")
                    elif action == 'mark_read':
                        client.mark_as_read(msg_id)
                        logging.info(f"Action 'mark_read' executed for {msg_id}")
                    elif action == 'archive':
                        client.archive(msg_id)
                        logging.info(f"Action 'archive' executed for {msg_id}")
                    elif action == 'star':
                        client.star(msg_id)
                        logging.info(f"Action 'star' executed for {msg_id}")

                # Record statistic
                self.db.record_stat(client.email_address, action, category)
            except Exception as e:
                logging.error(f"Failed to execute action {action} on {msg_id}: {e}")

    def process_message(self, gmail_client, msg_meta):
        """Process a single message for a specific client."""
        msg_id = msg_meta['id']

        if self.db.is_processed(msg_id, gmail_client.email_address):
            logging.info(f"Message {msg_id} already processed for {gmail_client.email_address}. Skipping.")
            return msg_id, None

        try:
            message = gmail_client.get_message(msg_id)
            category, actions = self.classifier.classify(message)

            logging.info(f"Message {msg_id} in {gmail_client.email_address} classified as: {category} with actions: {actions}")

            if actions:
                self.execute_actions(gmail_client, msg_id, category, actions)

            self.db.mark_as_processed(msg_id, account_email=gmail_client.email_address)
            return msg_id, category
        except Exception as e:
            logging.error(f"Error processing message {msg_id}: {e}")
            return msg_id, None

    def run_once(self):
        """Perform a single pass across all configured Gmail accounts."""
        all_tasks = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            for client in self.gmail_clients:
                logging.info(f"Checking for unread messages in account: {client.email_address}")
                try:
                    messages = client.list_unread_messages()
                    if not messages:
                        logging.info(f"No unread messages found for {client.email_address}")
                        continue

                    logging.info(f"Found {len(messages)} unread messages in {client.email_address}")
                    for msg in messages:
                        all_tasks.append(executor.submit(self.process_message, client, msg))
                except Exception as e:
                    logging.error(f"Error listing messages for {client.email_address}: {e}")

            for future in as_completed(all_tasks):
                msg_id, category = future.result()
                if category:
                    logging.info(f"Finished processing message {msg_id}")

    def run_forever(self, interval=60, start_dashboard=False):
        """Run the agent in a loop."""
        if start_dashboard:
            logging.info("Starting Dashboard thread...")
            dashboard_thread = threading.Thread(target=run_dashboard, daemon=True)
            dashboard_thread.start()

        logging.info(f"Starting MailAgent loop (Dry Run: {self.dry_run})...")
        while True:
            try:
                self.classifier.reload_rules()
                self.run_once()
            except Exception as e:
                logging.error(f"Error in MailAgent loop: {e}")

            logging.info(f"Sleeping for {interval} seconds...")
            time.sleep(interval)
