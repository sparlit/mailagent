import sys
import logging
import signal
import os
import json
from src.gmail_client import GmailClient
from src.classifier import EmailClassifier
from src.agent import MailAgent
from src.database import Database
from src.logger import setup_logging
from src import config

def signal_handler(sig, frame):
    logging.info("Interrupt received, shutting down gracefully...")
    sys.exit(0)

def migrate_accounts(db):
    """Migrate accounts from config/env to database if not already present."""
    accounts = config.get_accounts()
    for acc in accounts:
        # We use a placeholder email since we don't know it yet,
        # it will be updated when the client initializes.
        # But actually, we should try to avoid adding if we don't have a unique key.
        # For migration, we use the credentials/token path combination as a key if available.
        email_key = acc.get('credentials') or acc.get('token') or "default"

        # Check if already exists by checking get_accounts
        existing = db.get_accounts()
        if not any(e['credentials_path'] == acc.get('credentials') for e in existing):
            logging.info(f"Migrating account {email_key} to database.")
            db.add_account(
                email=email_key,
                credentials_path=acc.get('credentials'),
                token_path=acc.get('token')
            )

def main():
    setup_logging()
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    db = Database()

    # Perform migration
    migrate_accounts(db)

    try:
        db_accounts = db.get_accounts()
        gmail_clients = []

        for acc in db_accounts:
            try:
                client = GmailClient(
                    credentials_path=acc.get('credentials_path'),
                    token_path=acc.get('token_path')
                )

                # If the email was a placeholder, update it in DB
                if acc['email'] != client.email_address:
                    db.add_account(
                        email=client.email_address,
                        credentials_path=acc.get('credentials_path'),
                        token_path=acc.get('token_path'),
                        token_json=client._creds.to_json()
                    )
                    # Optionally remove the old placeholder
                    # db.remove_account(acc['email'])

                gmail_clients.append(client)
            except Exception as e:
                logging.error(f"Failed to initialize account {acc}: {e}")

        if not gmail_clients:
            logging.error("No valid Gmail accounts configured. Exiting.")
            sys.exit(1)

        classifier = EmailClassifier(rules_path=config.RULES_PATH)
        agent = MailAgent(gmail_clients, classifier, db, max_workers=config.MAX_WORKERS)

        agent.run_forever(interval=config.CHECK_INTERVAL, start_dashboard=True)
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
