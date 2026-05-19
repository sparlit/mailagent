import time
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from .gmail_client import GmailClient
from .classifier import EmailClassifier
from .database import Database
from .dashboard import run_dashboard
from . import config

class MailAgent:
    def __init__(self, gmail_clients: list[GmailClient], classifier: EmailClassifier, db: Database, max_workers=10, dry_run=None):
        """
        Create a MailAgent that processes messages from one or more Gmail accounts.
        
        Parameters:
            gmail_clients (list[GmailClient]): Gmail client instances to poll for unread messages.
            classifier (EmailClassifier): Component used to classify messages into categories and actions.
            db (Database): Persistence layer for processed-message state and statistics.
            max_workers (int): Maximum number of worker threads for concurrent message processing.
            dry_run (bool): If True, actions are only logged and not actually performed on Gmail accounts.
        """
        self.gmail_clients = gmail_clients
        self.classifier = classifier
        self.db = db
        self.max_workers = max_workers
        self.dry_run = dry_run if dry_run is not None else config.DRY_RUN

    def execute_actions(self, client, msg_id, category, actions):
        """
        Perform mailbox actions for a message and record corresponding statistics.
        
        Each action in `actions` is applied to the message identified by `msg_id` using `client`. When `self.dry_run` is true, actions are not performed and are only logged. Supported actions: 'trash', 'label', 'mark_read', 'archive', 'star', 'unstar', 'mark_important'. After each attempted action a statistic is recorded in `self.db`. Exceptions raised while performing an individual action are caught and logged; they do not stop processing remaining actions.
        
        Parameters:
            client: Gmail client instance used to perform mailbox operations and providing `email_address`.
            msg_id (str): Identifier of the message to act on.
            category (str): Category/label name used when applying a 'label' action and recorded with stats.
            actions (Iterable[str]): Sequence of action names to execute, evaluated in order.
        """
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
                    elif action == 'unstar':
                        client.unstar(msg_id)
                        logging.info(f"Action 'unstar' executed for {msg_id}")
                    elif action == 'mark_important':
                        client.mark_important(msg_id)
                        logging.info(f"Action 'mark_important' executed for {msg_id}")

                # Record statistic
                self.db.record_stat(client.email_address, action, category)
            except Exception as e:
                logging.error(f"Failed to execute action {action} on {msg_id}: {e}")

    def process_message(self, gmail_client, msg_meta):
        """
        Process a single Gmail message: classify it, execute any resulting actions, and mark it as processed.
        
        This method checks whether the message has already been processed for the given account; if so, it skips further work. Otherwise it fetches the message, obtains a classification and list of actions from the classifier, executes any actions, and records the message as processed. If an error occurs, the function returns with no category.
        
        Parameters:
            gmail_client: Gmail client instance for the account that provides message access and mutation methods.
            msg_meta (dict): Message metadata containing at least the key `'id'` with the message identifier.
        
        Returns:
            tuple: `(msg_id, category)` where `msg_id` is the message identifier and `category` is the classification label, or `None` if the message was skipped because it was already processed or processing failed.
        """
        msg_id = msg_meta['id']

        if self.db.is_processed(msg_id, account_email=gmail_client.email_address):
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
                try:
                    msg_id, category = future.result()
                    if category:
                        logging.info(f"Finished processing message {msg_id}")
                except Exception as e:
                    logging.error(f"Task generated an exception: {e}")

    def run_forever(self, interval=60, start_dashboard=None):
        """
        Run the MailAgent loop indefinitely, processing mail periodically.
        
        Each cycle reloads classifier rules, performs one sweep of all configured accounts, and then sleeps for the given interval. Exceptions raised during a cycle are logged and do not stop the loop. If start_dashboard is True, a dashboard is started in a separate daemon thread before the loop begins.
        
        Parameters:
            interval (int): Number of seconds to wait between cycles.
            start_dashboard (bool): If True, start the dashboard in a separate daemon thread before running.
        """
        should_start_dashboard = start_dashboard if start_dashboard is not None else config.DASHBOARD_ENABLED
        if should_start_dashboard:
            logging.info(f"Starting Dashboard thread on port {config.DASHBOARD_PORT}...")
            dashboard_thread = threading.Thread(
                target=run_dashboard,
                kwargs={'port': config.DASHBOARD_PORT},
                daemon=True
            )
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
