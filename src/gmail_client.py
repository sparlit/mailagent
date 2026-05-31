import os
import os.path
import re
import time
import random
import threading
import logging
import json
import base64
from email.message import EmailMessage
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from typing import List, Optional, Iterable, Dict, Any, Union

__all__ = ['GmailClient', 'MockGmailClient']

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.modify', 'https://www.googleapis.com/auth/gmail.send']

def retry_with_backoff(max_retries=5):
    """
    Exponential backoff decorator for retrying functions on specific API errors.
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except HttpError as error:
                    if error.resp.status in [429, 500, 502, 503, 504]:
                        wait_time = (2 ** retries) + random.random()
                        logging.warning(f"Retry {retries + 1}/{max_retries} after {wait_time:.2f}s due to error: {error}")
                        time.sleep(wait_time)
                        retries += 1
                    else:
                        raise
            return func(*args, **kwargs)
        return wrapper
    return decorator

class GmailClient:
    _thread_local = threading.local()

    def __init__(self, credentials_path: str = 'credentials.json', token_path: str = 'token.json') -> None:
        """
        Initialize the GmailClient.

        Parameters:
            credentials_path (str): Path to the OAuth 2.0 client secrets file.
            token_path (str): Path to the user's authorized token file.
        """
        self.credentials_path = credentials_path
        self.token_path = token_path
        self._creds = self._load_credentials()
        self._labels_cache = None
        self._labels_lock = threading.Lock()
        self.email_address = self._get_user_email()

    def _get_user_email(self) -> str:
        """Return the authenticated user's email address."""
        try:
            profile = self.service.users().getProfile(userId='me').execute()
            email = profile.get('emailAddress')
            if not email:
                logging.warning("User profile fetched but emailAddress is missing.")
                return "unknown"
            return email
        except Exception as e:
            logging.error(f"Error fetching user profile: {e}")
            return "unknown"

    @staticmethod
    def _get_body_text(payload):
        """
        Recursively extract text from a Gmail message payload.
        Prioritizes text/plain, falls back to text/html (stripped).

        Parameters:
            payload (dict): Gmail message payload or part.

        Returns:
            str: Extracted plain text content.
        """
        body_text = ""
        html_text = ""
        parts = payload.get('parts', [])

        if not parts:
            mime_type = payload.get('mimeType')
            data = payload.get('body', {}).get('data', '')
            if data:
                try:
                    decoded = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                    if mime_type == 'text/plain':
                        return decoded
                    elif mime_type == 'text/html':
                        return re.sub('<[^<]+?>', '', decoded)
                except Exception:
                    pass
            return ""

        for part in parts:
            mime_type = part.get('mimeType')
            data = part.get('body', {}).get('data', '')

            if mime_type == 'text/plain' and data:
                try:
                    body_text += base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                except Exception:
                    pass
            elif mime_type == 'text/html' and data:
                try:
                    decoded_html = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                    html_text += re.sub('<[^<]+?>', '', decoded_html)
                except Exception:
                    pass
            elif mime_type.startswith('multipart/'):
                body_text += GmailClient._get_body_text(part)

        return body_text if body_text.strip() else html_text.strip()

    def _load_credentials(self) -> Credentials:
        """Load or refresh the OAuth 2.0 credentials."""
        creds = None
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)

        if not creds:
            env_token = os.getenv(f'GMAIL_TOKEN_{os.path.basename(self.token_path).upper().replace(".", "_")}')
            if env_token:
                try:
                    token_data = json.loads(env_token)
                    creds = Credentials.from_authorized_user_info(token_data, SCOPES)
                    logging.info(f"Loaded credentials from environment for {self.token_path}")
                except Exception as e:
                    logging.error(f"Failed to load credentials from environment: {e}")

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if os.path.exists(self.credentials_path):
                    flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, SCOPES)
                else:
                    env_creds = os.getenv(f'GMAIL_CREDENTIALS_{os.path.basename(self.credentials_path).upper().replace(".", "_")}')
                    if env_creds:
                        try:
                            creds_data = json.loads(env_creds)
                            flow = InstalledAppFlow.from_client_config(creds_data, SCOPES)
                        except Exception as e:
                            logging.error(f"Failed to load credentials from env: {e}")
                            raise FileNotFoundError(f"Credentials file not found at {self.credentials_path}")
                    else:
                        raise FileNotFoundError(f"Credentials file not found at {self.credentials_path}")

                creds = flow.run_local_server(port=0)

            with open(self.token_path, 'w') as token:
                token.write(creds.to_json())

        return creds

    @property
    def service(self) -> Any:
        """Thread-safe Gmail API service."""
        if not hasattr(self._thread_local, "service"):
            self._thread_local.service = build('gmail', 'v1', credentials=self._creds)
        return self._thread_local.service

    def _get_labels(self) -> Dict[str, str]:
        """Thread-safe label caching."""
        with self._labels_lock:
            if self._labels_cache is None:
                results = self.service.users().labels().list(userId='me').execute()
                labels = results.get('labels', [])
                self._labels_cache = {label['name']: label['id'] for label in labels}
        return self._labels_cache

    @retry_with_backoff()
    def list_unread_messages(self, user_id: str = 'me') -> List[Dict[str, str]]:
        """List all unread messages, handling pagination."""
        with self._labels_lock:
            self._labels_cache = None

        messages = []
        next_page_token = None
        while True:
            results = self.service.users().messages().list(
                userId=user_id, q='is:unread', pageToken=next_page_token
            ).execute()
            messages.extend(results.get('messages', []))
            next_page_token = results.get('nextPageToken')
            if not next_page_token:
                break
        return messages

    @retry_with_backoff()
    def get_message(self, message_id: str, user_id: str = 'me') -> Dict[str, Any]:
        """Get a specific message by ID, including the full payload."""
        return self.service.users().messages().get(userId=user_id, id=message_id, format='full').execute()

    @retry_with_backoff()
    def _modify_message_labels(self, message_id: str, add_label_ids: Optional[List[str]] = None, remove_label_ids: Optional[List[str]] = None, user_id: str = 'me') -> Dict[str, Any]:
        """Helper to modify message labels using batchModify."""
        body = {'ids': [message_id]}
        if add_label_ids: body['addLabelIds'] = add_label_ids
        if remove_label_ids: body['removeLabelIds'] = remove_label_ids
        return self.service.users().messages().batchModify(userId=user_id, body=body).execute()

    def mark_as_read(self, message_id: str, user_id: str = 'me') -> Dict[str, Any]:
        """Mark a message as read by removing the UNREAD label."""
        return self._modify_message_labels(message_id, remove_label_ids=['UNREAD'], user_id=user_id)

    def move_to_trash(self, message_id: str, user_id: str = 'me') -> Dict[str, Any]:
        """Move a message to the trash."""
        return self.service.users().messages().trash(userId=user_id, id=message_id).execute()

    def archive(self, message_id: str, user_id: str = 'me') -> Dict[str, Any]:
        """Archive a message by removing the INBOX label."""
        return self._modify_message_labels(message_id, remove_label_ids=['INBOX'], user_id=user_id)

    def star(self, message_id: str, user_id: str = 'me') -> Dict[str, Any]:
        """Star a message by adding the STARRED label."""
        return self._modify_message_labels(message_id, add_label_ids=['STARRED'], user_id=user_id)

    def unstar(self, message_id: str, user_id: str = 'me') -> Dict[str, Any]:
        """Unstar a message by removing the STARRED label."""
        return self._modify_message_labels(message_id, remove_label_ids=['STARRED'], user_id=user_id)

    def mark_important(self, message_id: str, user_id: str = 'me') -> Dict[str, Any]:
        """Mark a message as important by adding the IMPORTANT label."""
        return self._modify_message_labels(message_id, add_label_ids=['IMPORTANT'], user_id=user_id)

    @retry_with_backoff()
    def forward_message(self, message_id: str, to: str, user_id: str = 'me') -> Dict[str, Any]:
        """Forward a message to another recipient."""
        original_msg = self.get_message(message_id, user_id=user_id)
        body = self._get_body_text(original_msg.get('payload', {})) or original_msg.get('snippet', '')
        subject = 'Fwd: (no subject)'
        for header in original_msg.get('payload', {}).get('headers', []):
            if header['name'].lower() == 'subject':
                subject = 'Fwd: ' + header['value']
                break
        message = EmailMessage()
        message.set_content(f"Forwarded message content:\n\n{body}\n\n--- Sent by MailAgent ---")
        message['To'] = to
        message['From'] = self.email_address
        message['Subject'] = subject
        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        return self.service.users().messages().send(userId=user_id, body={'raw': encoded_message}).execute()

    @retry_with_backoff()
    def send_reply(self, original_message_id: str, subject: str, body: str, user_id: str = 'me') -> Dict[str, Any]:
        """Send a reply to an existing message, maintaining the thread."""
        original_msg = self.get_message(original_message_id, user_id=user_id)
        thread_id = original_msg.get('threadId')
        headers = {h['name'].lower(): h['value'] for h in original_msg.get('payload', {}).get('headers', [])}
        message_id_header = headers.get('message-id')
        references = headers.get('references', '')
        to = headers.get('reply-to', headers.get('from'))
        reply = EmailMessage()
        reply.set_content(body)
        reply['To'] = to
        reply['From'] = self.email_address
        reply['Subject'] = subject
        reply['In-Reply-To'] = message_id_header
        reply['References'] = f"{references} {message_id_header}".strip()
        encoded_message = base64.urlsafe_b64encode(reply.as_bytes()).decode()
        return self.service.users().messages().send(userId=user_id, body={'raw': encoded_message, 'threadId': thread_id}).execute()

    @retry_with_backoff()
    def apply_labels(self, message_id: str, label_ids: Iterable[str], user_id: str = 'me') -> Optional[Dict[str, Any]]:
        """Apply labels to a message, creating them if necessary."""
        existing_label_names = self._get_labels()
        final_label_ids = []
        for label_name in label_ids:
            if label_name in existing_label_names:
                final_label_ids.append(existing_label_names[label_name])
            elif label_name in ['INBOX', 'SPAM', 'TRASH', 'UNREAD', 'STARRED', 'IMPORTANT']:
                final_label_ids.append(label_name)
            else:
                try:
                    new_label = self.service.users().labels().create(userId=user_id, body={'name': label_name}).execute()
                    label_id = new_label['id']
                    final_label_ids.append(label_id)
                    with self._labels_lock: self._labels_cache[label_name] = label_id
                except Exception as e:
                    logging.error(f"Error creating label {label_name}: {e}")
        if not final_label_ids: return None
        return self._modify_message_labels(message_id, add_label_ids=final_label_ids, user_id=user_id)

class MockGmailClient(GmailClient):
    """Mock Gmail client for dry-run environments."""
    def __init__(self, credentials_path='credentials.json', token_path='token.json'):
        self.credentials_path, self.token_path = credentials_path, token_path
        self.email_address = f"mock_{os.path.basename(token_path).split('.')[0]}@example.com"
        self._labels_cache = {"INBOX": "INBOX", "UNREAD": "UNREAD"}
    @property
    def service(self): return None
    def _get_user_email(self): return self.email_address
    def _load_credentials(self): return None
    def list_unread_messages(self, user_id='me'): return [{'id': f'mock_msg_{i}'} for i in range(1, 4)]
    def get_message(self, message_id, user_id='me'):
        return {'id': message_id, 'snippet': 'Mock snippet', 'payload': {'headers': [{'name': 'Subject', 'value': 'Mock'}, {'name': 'From', 'value': 'a@b.com'}]}}
    def mark_as_read(self, message_id, user_id='me'): return {}
    def move_to_trash(self, message_id, user_id='me'): return {}
    def archive(self, message_id, user_id='me'): return {}
    def star(self, message_id, user_id='me'): return {}
    def unstar(self, message_id, user_id='me'): return {}
    def mark_important(self, message_id, user_id='me'): return {}
    def forward_message(self, message_id, to, user_id='me'): return {}
    def apply_labels(self, message_id, label_ids, user_id='me'): return {}
