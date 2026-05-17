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
        """
        Initialize the MailAgent with Gmail account clients, a classifier, and persistence/configuration.
        
        Parameters:
            gmail_clients (list[GmailClient]): Gmail client instances to poll and operate on.
            classifier (EmailClassifier): Component used to classify fetched messages into categories and actions.
            db (Database): Persistence layer for recording per-message processed state and action statistics.
            max_workers (int): Maximum number of worker threads for concurrent message processing.
            dry_run (bool): If True, do not perform any mutating Gmail operations; actions are only logged.
        """
        self.gmail_clients = gmail_clients
        self.classifier = classifier
        self.db = db
        self.max_workers = max_workers
        self.dry_run = dry_run

    def execute_actions(self, client, msg_id, category, actions):
        """
        Execute configured Gmail actions for a single message and record per-action statistics.
        
        For each action in `actions`, perform the corresponding operation on `client` (or log the intended action when the agent is in dry-run mode) and record a statistic for that action and category. Failures for an individual action are caught and logged; remaining actions continue to run.
        
        Parameters:
            client: Gmail client object used to perform actions; expected to expose `email_address` and methods like `move_to_trash`, `apply_labels`, `mark_as_read`, `archive`, and `star`.
            msg_id (str): Identifier of the message to act upon.
            category (str): Category/label name used when applying labels and for recorded statistics.
            actions (Iterable[str]): Sequence of action names to execute. Supported values: `'trash'`, `'label'`, `'mark_read'`, `'archive'`, `'star'`.
        """
        for action in actions:
            try:
                if self.dry_run:
                    logging.info(f"[DRY RUN] Would execute {action} for {msg_id}")
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
        """
        Process a single Gmail message for a specific account.
        
        Classifies the message, executes any actions returned by the classifier, and marks the message as processed to prevent future handling. If the message was already marked processed or an error occurs during handling, no actions are executed.
        
        Parameters:
        	msg_meta (dict): Message metadata containing at least the key `'id'` with the Gmail message ID.
        
        Returns:
        	tuple: `(msg_id, category)` where `msg_id` is the message ID and `category` is the classification label, or `None` if the message was skipped because it was already processed or an error occurred.
        """
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
        """
        Scan all configured Gmail accounts once and process their unread messages.
        
        Submits a processing task for each unread message to a ThreadPoolExecutor, waits for all tasks to complete, logs progress for each account and message, and records any errors encountered while listing messages.
        """
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
        """
        Continuously poll configured Gmail accounts to classify unread messages and perform configured actions on a repeating interval.
        
        Runs indefinitely until the process is stopped; each loop reloads classifier rules, performs one polling/processing cycle, then sleeps for `interval` seconds.
        
        Parameters:
            interval (int): Seconds to wait between iterations of the processing loop.
            start_dashboard (bool): If True, start the dashboard in a background daemon thread before entering the loop.
        """
        if start_dashboard:
            logging.info("Starting Dashboard thread...")
            dashboard_thread = threading.Thread(target=run_dashboard, daemon=True)
            dashboard_thread.start()

        logging.info("Starting MailAgent loop with persistence, stats and dynamic actions...")
        while True:
            try:
                self.classifier.reload_rules()
                self.run_once()
            except Exception as e:
                logging.error(f"Error in MailAgent loop: {e}")

            logging.info(f"Sleeping for {interval} seconds...")
            time.sleep(interval)
