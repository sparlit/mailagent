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
    logging.info("Interrupt received, shutting down gracefully...")
    sys.exit(0)

def main():
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
