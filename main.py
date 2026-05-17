import sys
import logging
from src.gmail_client import GmailClient
from src.classifier import EmailClassifier
from src.agent import MailAgent
from src import config

def main():
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

        classifier = EmailClassifier(rules_path=config.RULES_PATH)
        agent = MailAgent(gmail_clients, classifier, max_workers=config.MAX_WORKERS)

        agent.run_forever(interval=config.CHECK_INTERVAL)
    except KeyboardInterrupt:
        print("\nStopping MailAgent...")
        sys.exit(0)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
