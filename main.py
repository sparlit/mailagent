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
    Handle termination signals and shut down the process gracefully.
    
    Logs an informational message and exits the process with status code 0.
    
    Parameters:
        sig (int): Signal number received by the handler.
        frame (frame object): Current stack frame when the signal was received.
    """
    logging.info("Interrupt received, shutting down gracefully...")
    sys.exit(0)

def main():
    """
    Start the mail-processing service: configure logging and signal handlers, initialize Gmail clients and supporting components, and run the agent's continuous processing loop.
    
    This function configures logging and registers handlers for SIGINT/SIGTERM, loads configured Gmail accounts and initializes clients (skipping accounts that fail to initialize), constructs the Database, EmailClassifier, and MailAgent, and then starts the agent's long-running processing loop. If no Gmail clients are successfully initialized or an unexpected error occurs during startup, the process exits with a non-zero status.
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
