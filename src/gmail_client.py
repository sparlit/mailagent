import os
import os.path
import time
import random
import threading
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

def retry_with_backoff(max_retries=5):
    def decorator(func):
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except HttpError as error:
                    if error.resp.status in [429, 500, 502, 503, 504]:
                        wait_time = (2 ** retries) + random.random()
                        print(f"Retry {retries + 1}/{max_retries} after {wait_time:.2f}s due to error: {error}")
                        time.sleep(wait_time)
                        retries += 1
                    else:
                        raise
            return func(*args, **kwargs)
        return wrapper
    return decorator

class GmailClient:
    _thread_local = threading.local()

    def __init__(self, credentials_path='credentials.json', token_path='token.json'):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self._creds = self._load_credentials()
        self._labels_cache = None
        self._labels_lock = threading.Lock()

    def _load_credentials(self):
        creds = None
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.credentials_path):
                    raise FileNotFoundError(f"Credentials file not found at {self.credentials_path}")
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)
            with open(self.token_path, 'w') as token:
                token.write(creds.to_json())
        return creds

    @property
    def service(self):
        """Thread-safe Gmail API service."""
        if not hasattr(self._thread_local, "service"):
            self._thread_local.service = build('gmail', 'v1', credentials=self._creds)
        return self._thread_local.service

    def _get_labels(self):
        """Thread-safe label caching."""
        with self._labels_lock:
            if self._labels_cache is None:
                results = self.service.users().labels().list(userId='me').execute()
                labels = results.get('labels', [])
                self._labels_cache = {label['name']: label['id'] for label in labels}
        return self._labels_cache

    @retry_with_backoff()
    def list_unread_messages(self, user_id='me'):
        """List all unread messages, handling pagination."""
        # Invalidate cache at the start of a run to catch any new labels
        with self._labels_lock:
            self._labels_cache = None

        messages = []
        next_page_token = None

        while True:
            results = self.service.users().messages().list(
                userId=user_id,
                q='is:unread',
                pageToken=next_page_token
            ).execute()

            messages.extend(results.get('messages', []))
            next_page_token = results.get('nextPageToken')

            if not next_page_token:
                break

        return messages

    @retry_with_backoff()
    def get_message(self, message_id, user_id='me'):
        """Get a specific message by ID."""
        return self.service.users().messages().get(userId=user_id, id=message_id).execute()

    @retry_with_backoff()
    def mark_as_read(self, message_id, user_id='me'):
        """Mark a message as read by removing the UNREAD label."""
        return self.service.users().messages().batchModify(
            userId=user_id,
            body={
                'ids': [message_id],
                'removeLabelIds': ['UNREAD']
            }
        ).execute()

    @retry_with_backoff()
    def move_to_trash(self, message_id, user_id='me'):
        """Move a message to trash."""
        return self.service.users().messages().trash(userId=user_id, id=message_id).execute()

    @retry_with_backoff()
    def apply_labels(self, message_id, label_ids, user_id='me'):
        """Apply specific labels to a message, creating them if they don't exist."""
        existing_label_names = self._get_labels()

        final_label_ids = []
        for label_name in label_ids:
            if label_name in existing_label_names:
                final_label_ids.append(existing_label_names[label_name])
            elif label_name in ['INBOX', 'SPAM', 'TRASH', 'UNREAD', 'STARRED', 'IMPORTANT', 'SENT', 'DRAFT', 'CATEGORY_PERSONAL', 'CATEGORY_SOCIAL', 'CATEGORY_PROMOTIONS', 'CATEGORY_UPDATES', 'CATEGORY_FORUMS']:
                final_label_ids.append(label_name)
            else:
                try:
                    new_label = self.service.users().labels().create(
                        userId=user_id,
                        body={'name': label_name}
                    ).execute()
                    label_id = new_label['id']
                    final_label_ids.append(label_id)
                    # Update cache
                    with self._labels_lock:
                        self._labels_cache[label_name] = label_id
                except Exception as e:
                    print(f"Error creating label {label_name}: {e}")

        if not final_label_ids:
            return

        return self.service.users().messages().batchModify(
            userId=user_id,
            body={
                'ids': [message_id],
                'addLabelIds': final_label_ids
            }
        ).execute()
