import os
import os.path
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

__all__ = ['GmailClient']

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.modify', 'https://www.googleapis.com/auth/gmail.send']

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

    def __init__(self, credentials_path='credentials.json', token_path='token.json'):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self._creds = self._load_credentials()
        self._labels_cache = None
        self._labels_lock = threading.Lock()
        self.email_address = self._get_user_email()

    def _get_user_email(self):
        """
        Return the authenticated user's email address.
        
        Returns:
            email (str): The user's email address; returns "unknown" if the profile lacks an emailAddress or if an error occurs while fetching the profile.
        """
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

    def _load_credentials(self):
        creds = None
        # Try loading from token_path
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)

        # Fallback to environment variable for headless environments
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
                if not os.path.exists(self.credentials_path):
                    raise FileNotFoundError(f"Credentials file not found at {self.credentials_path}")
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)

            # Save the credentials
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

    def _get_body_text(self, payload):
        """
        Recursively extract plain text from a message payload.

        Parameters:
            payload (dict): The message payload from Gmail API.

        Returns:
            str: Extracted plain text body.
        """
        body_text = ""
        parts = payload.get('parts', [])

        # If there are no parts, check the body data directly
        if not parts:
            data = payload.get('body', {}).get('data')
            if data:
                try:
                    decoded_data = base64.urlsafe_b64decode(data).decode('utf-8')
                    if payload.get('mimeType') == 'text/plain':
                        body_text += decoded_data
                except Exception as e:
                    logging.error(f"Error decoding body data: {e}")
        else:
            for part in parts:
                if part.get('mimeType') == 'text/plain':
                    data = part.get('body', {}).get('data')
                    if data:
                        try:
                            body_text += base64.urlsafe_b64decode(data).decode('utf-8')
                        except Exception as e:
                            logging.error(f"Error decoding part data: {e}")
                elif part.get('mimeType') == 'multipart/alternative' or part.get('parts'):
                    body_text += self._get_body_text(part)

        return body_text

    @retry_with_backoff()
    def _modify_message_labels(self, message_id, add_label_ids=None, remove_label_ids=None, user_id='me'):
        """
        Internal helper to modify labels on a message using batchModify.

        Parameters:
            message_id (str): The ID of the message to modify.
            add_label_ids (list, optional): List of label IDs to add.
            remove_label_ids (list, optional): List of label IDs to remove.
            user_id (str): User identifier. Defaults to 'me'.

        Returns:
            dict: The Gmail API response.
        """
        body = {'ids': [message_id]}
        if add_label_ids:
            body['addLabelIds'] = add_label_ids
        if remove_label_ids:
            body['removeLabelIds'] = remove_label_ids

        return self.service.users().messages().batchModify(
            userId=user_id,
            body=body
        ).execute()

    @retry_with_backoff()
    def mark_as_read(self, message_id, user_id='me'):
        """Mark a message as read by removing the UNREAD label."""
        return self._modify_message_labels(message_id, remove_label_ids=['UNREAD'], user_id=user_id)

    @retry_with_backoff()
    def move_to_trash(self, message_id, user_id='me'):
        """
        Moves the specified message to the Trash.
        
        Returns:
            dict: The Gmail API response for the trashed message.
        """
        return self.service.users().messages().trash(userId=user_id, id=message_id).execute()

    @retry_with_backoff()
    def archive(self, message_id, user_id='me'):
        """
        Archive a message by removing the `INBOX` label.
        
        Returns:
            response (dict): The Gmail API response returned by the `batchModify` call.
        """
        return self._modify_message_labels(message_id, remove_label_ids=['INBOX'], user_id=user_id)

    @retry_with_backoff()
    def star(self, message_id, user_id='me'):
        """
        Star a message by adding Gmail's `STARRED` label.
        
        Returns:
            dict: The Gmail API response for the `batchModify` request.
        """
        return self._modify_message_labels(message_id, add_label_ids=['STARRED'], user_id=user_id)

    @retry_with_backoff()
    def unstar(self, message_id, user_id='me'):
        """
        Remove the STARRED label from a message.

        Returns:
            dict: The Gmail API response.
        """
        return self._modify_message_labels(message_id, remove_label_ids=['STARRED'], user_id=user_id)

    @retry_with_backoff()
    def mark_important(self, message_id, user_id='me'):
        """
        Add the IMPORTANT label to a message.

        Returns:
            dict: The Gmail API response.
        """
        return self._modify_message_labels(message_id, add_label_ids=['IMPORTANT'], user_id=user_id)

    @retry_with_backoff()
    def forward_message(self, message_id, to, user_id='me'):
        """
        Forward a message's snippet to another recipient.

        Parameters:
            message_id (str): ID of the message to forward.
            to (str): Recipient email address.
            user_id (str): User identifier.

        Returns:
            dict: The Gmail API response for the sent message.
        """
        original_msg = self.get_message(message_id, user_id=user_id)
        snippet = original_msg.get('snippet', '')
        subject = 'Fwd: (no subject)'

        for header in original_msg.get('payload', {}).get('headers', []):
            if header['name'].lower() == 'subject':
                subject = 'Fwd: ' + header['value']
                break

        message = EmailMessage()
        message.set_content(f"Forwarded message snippet:\n\n{snippet}\n\n--- Sent by MailAgent ---")
        message['To'] = to
        message['From'] = self.email_address
        message['Subject'] = subject

        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        return self.service.users().messages().send(userId=user_id, body={'raw': encoded_message}).execute()

    @retry_with_backoff()
    def reply_to_message(self, message_id, body_text, user_id='me'):
        """
        Send a reply to a message.

        Parameters:
            message_id (str): ID of the message to reply to.
            body_text (str): The text content of the reply.
            user_id (str): User identifier.

        Returns:
            dict: The Gmail API response for the sent message.
        """
        original_msg = self.get_message(message_id, user_id=user_id)
        headers = original_msg.get('payload', {}).get('headers', [])

        subject = "Re: (no subject)"
        to_email = ""
        message_id_header = ""
        references_header = ""

        for header in headers:
            name = header['name'].lower()
            if name == 'subject':
                subject = header['value']
                if not subject.lower().startswith('re:'):
                    subject = "Re: " + subject
            elif name == 'from':
                to_email = header['value']
            elif name == 'message-id':
                message_id_header = header['value']
            elif name == 'references':
                references_header = header['value']

        reply = EmailMessage()
        reply.set_content(body_text)
        reply['To'] = to_email
        reply['From'] = self.email_address
        reply['Subject'] = subject
        reply['In-Reply-To'] = message_id_header

        references = (references_header + " " + message_id_header).strip()
        reply['References'] = references

        thread_id = original_msg.get('threadId')
        encoded_message = base64.urlsafe_b64encode(reply.as_bytes()).decode()

        return self.service.users().messages().send(
            userId=user_id,
            body={
                'raw': encoded_message,
                'threadId': thread_id
            }
        ).execute()

    @retry_with_backoff()
    def apply_labels(self, message_id, label_ids, user_id='me'):
        """
        Apply labels to the specified message, creating any custom labels that do not yet exist.
        
        Parameters:
        	message_id (str): ID of the message to modify.
        	label_ids (Iterable[str]): Iterable of label names to apply; system/category labels may be provided directly (e.g., 'INBOX', 'STARRED').
        	user_id (str): User identifier, typically `'me'`.
        
        Returns:
        	dict or None: The Gmail API `batchModify` response when labels were applied, or `None` if no labels were resolved/applied.
        """
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
                    with self._labels_lock:
                        self._labels_cache[label_name] = label_id
                except Exception as e:
                    logging.error(f"Error creating label {label_name}: {e}")

        if not final_label_ids:
            return

        return self._modify_message_labels(message_id, add_label_ids=final_label_ids, user_id=user_id)
