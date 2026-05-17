import time
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from .gmail_client import GmailClient
from .classifier import EmailClassifier
from .database import Database
from .dashboard import run_dashboard

class MailAgent:
    def __init__(self, gmail_clients: list[GmailClient], classifier: EmailClassifier, db: Database, max_workers=10):
        """
        Initialize the MailAgent.
        
        Parameters:
            gmail_clients (list[GmailClient]): Gmail client instances representing accounts to poll for unread messages.
            classifier (EmailClassifier): Classifier that returns a message category and list of actions for a message.
            db (Database): Persistence layer used to check/mark processed messages and record per-action statistics.
            max_workers (int): Maximum number of worker threads used for concurrent message processing.
        """
        self.gmail_clients = gmail_clients
        self.classifier = classifier
        self.db = db
        self.max_workers = max_workers

    def execute_actions(self, client, msg_id, category, actions):
        """
        Execute the provided actions for a single message and record per-action statistics.
        
        Parameters:
            client: Gmail client used to perform mailbox operations (e.g., move to trash, apply labels, mark as read).
            msg_id (str): Identifier of the message to act on.
            category (str): Classification label applied when performing label-related actions and recorded with stats.
            actions (Iterable[str]): Sequence of actions to perform; expected values include 'trash', 'label', and 'mark_read'.
        
        Notes:
            - Each action is attempted independently; failures for individual actions are caught and logged, and do not stop other actions.
            - For each successfully attempted action a statistic is recorded via the agent's database.
        """
        for action in actions:
            try:
                if action == 'trash':
                    client.move_to_trash(msg_id)
                    logging.info(f"Action 'trash' executed for {msg_id}")
                elif action == 'label':
                    client.apply_labels(msg_id, [category])
                    logging.info(f"Action 'label' ({category}) executed for {msg_id}")
                elif action == 'mark_read':
                    client.mark_as_read(msg_id)
                    logging.info(f"Action 'mark_read' executed for {msg_id}")

                # Record statistic
                self.db.record_stat(client.email_address, action, category)
            except Exception as e:
                logging.error(f"Failed to execute action {action} on {msg_id}: {e}")

    def process_message(self, gmail_client, msg_meta):
        """
        Process a single message for a specific Gmail client and apply any resulting actions.
        
        If the message has already been recorded as processed, no actions are taken and the message is skipped. Otherwise the message is fetched, classified, any returned actions are executed, and the message is marked as processed in the database.
        
        Parameters:
            gmail_client: GmailClient-like object used to fetch and mutate the message; must expose `email_address`, `get_message(msg_id)`, and action methods used by `execute_actions`.
            msg_meta (dict): Message metadata containing at least the key `'id'` with the message identifier.
        
        Returns:
            tuple: `(msg_id, category)` where `msg_id` is the message identifier and `category` is the classification label if processing completed; `category` is `None` when the message was skipped or an error occurred.
        """
        msg_id = msg_meta['id']

        if self.db.is_processed(msg_id):
            logging.info(f"Message {msg_id} already processed. Skipping.")
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
        Perform a single pass across all configured Gmail accounts, listing unread messages and concurrently processing each message.
        
        For each account, unread messages are listed; if any are found, a processing task is submitted for each message and this method waits for all submitted tasks to complete. Listing errors for an account are logged and do not propagate. When a message is processed and classified, a completion log entry is emitted.
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
        Continuously run the MailAgent, repeatedly invoking run_once and sleeping between iterations.
        
        If start_dashboard is True, starts the dashboard in a background daemon thread before entering the loop. Each loop iteration calls run_once; exceptions raised by run_once are caught and logged but do not stop the loop. The agent sleeps for `interval` seconds between iterations.
        
        Parameters:
            interval (int): Number of seconds to sleep between iterations.
            start_dashboard (bool): If True, start the dashboard thread before entering the loop.
        """
        if start_dashboard:
            logging.info("Starting Dashboard thread...")
            dashboard_thread = threading.Thread(target=run_dashboard, daemon=True)
            dashboard_thread.start()

        logging.info("Starting MailAgent loop with persistence, stats and dynamic actions...")
        while True:
            try:
                self.run_once()
            except Exception as e:
                logging.error(f"Error in MailAgent loop: {e}")

            logging.info(f"Sleeping for {interval} seconds...")
            time.sleep(interval)
