import sys
from src.gmail_client import GmailClient
from src.classifier import EmailClassifier
from src.agent import MailAgent
from src import config

def main():
    try:
        gmail_client = GmailClient(
            credentials_path=config.CREDENTIALS_PATH,
            token_path=config.TOKEN_PATH
        )
        classifier = EmailClassifier()
        agent = MailAgent(gmail_client, classifier)

        agent.run_forever(interval=config.CHECK_INTERVAL)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Please ensure credentials.json is present in the project root.")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nStopping MailAgent...")
        sys.exit(0)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
