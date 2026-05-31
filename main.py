import sys
import logging
import signal
from src.gmail_client import GmailClient, MockGmailClient
from src.classifier import EmailClassifier
from src.agent import MailAgent
from src.database import Database
from src.logger import setup_logging
from src import config

def signal_handler(sig, frame):
    logging.info("Interrupt received, shutting down gracefully...")
    sys.exit(0)

def main():
    """
    Bootstrap and run the mail-processing application.
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
                if config.DRY_RUN:
                    logging.warning(f"Failed to initialize Gmail account {acc}, falling back to MockGmailClient for DRY_RUN: {e}")
                    client = MockGmailClient(
                        credentials_path=acc.get('credentials'),
                        token_path=acc.get('token')
                    )
                    gmail_clients.append(client)
                else:
                    logging.error(f"Failed to initialize account {acc}: {e}")
                    logging.error("Ensure 'credentials.json' exists in the root or is provided via GMAIL_CREDENTIALS_CREDENTIALS_JSON env var.")

        if not gmail_clients:
            logging.error("No valid Gmail accounts could be initialized. Please check your credentials and configuration.")
            logging.error("Refer to README.md for setup instructions and environment variable configuration.")
            sys.exit(1)

        db = Database()
        classifier = EmailClassifier(rules_path=config.RULES_PATH)
        agent = MailAgent(
            gmail_clients,
            classifier,
            db,
            max_workers=config.MAX_WORKERS,
            dry_run=config.DRY_RUN
        )

        agent.run_forever(
            interval=config.CHECK_INTERVAL,
            start_dashboard=config.DASHBOARD_ENABLED
        )
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
