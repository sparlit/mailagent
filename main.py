import sys
import logging
import signal
from src.gmail_client import GmailClient
from src.classifier import EmailClassifier
from src.agent import MailAgent
from src.database import Database
from src.logger import setup_logging
from src import config

def signal_handler(sig, frame):
    """
    Handle termination signals by logging an informational shutdown message and exiting the process with status code 0.
    
    Parameters:
        sig (int): The signal number received (e.g., SIGINT, SIGTERM).
        frame (types.FrameType | None): The current stack frame or None.
    """
    logging.info("Interrupt received, shutting down gracefully...")
    sys.exit(0)

def main():
    """
    Configure runtime components and start the mail processing agent loop.
    
    Sets up logging and installs SIGINT/SIGTERM handlers for graceful shutdown. Loads Gmail account configurations and attempts to initialize a Gmail client for each account, logging and skipping accounts that fail to initialize. If no clients are successfully created, exits the process with status code 1. On success, constructs the Database, an EmailClassifier (using config.RULES_PATH), and a MailAgent (using config.MAX_WORKERS), then starts the agent's continuous processing loop with interval config.CHECK_INTERVAL. Logs any unexpected startup error and exits the process with status code 1.
    """
    setup_logging()
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        accounts = config.get_accounts()
        gmail_clients = []

        for acc in accounts:
            try:
                client = GmailClient(
                    credentials_path=acc.get('credentials'),
                    token_path=acc.get('token')
                )
                gmail_clients.append(client)
            except Exception as e:
                logging.error(f"Failed to initialize account {acc}: {e}")

        if not gmail_clients:
            logging.error("No valid Gmail accounts configured. Exiting.")
            sys.exit(1)

        db = Database()
        classifier = EmailClassifier(rules_path=config.RULES_PATH)
        agent = MailAgent(gmail_clients, classifier, db, max_workers=config.MAX_WORKERS)

        agent.run_forever(interval=config.CHECK_INTERVAL)
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
