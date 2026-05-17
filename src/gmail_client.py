import os
import os.path
import time
import random
import threading
import logging
import json
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

def retry_with_backoff(max_retries=5):
    """
    Decorator factory that retries a wrapped function on transient Gmail API HTTP errors using exponential backoff with jitter.
    
    The returned decorator wraps a callable and, when the callable raises googleapiclient.errors.HttpError with an HTTP status of 429, 500, 502, 503, or 504, retries the call up to `max_retries` times with exponential backoff and a random jitter. If the HttpError has any other status, it is re-raised immediately. After exhausting retries, the wrapper makes one final call and returns its result or raises any error it produces.
    
    Parameters:
        max_retries (int): Maximum number of retry attempts before performing one final call (default 5).
    
    Returns:
        function: A decorator that produces a retrying wrapper for the target callable.
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

    def __init__(self, credentials_path='credentials.json', token_path='token.json'):
        """
        Initialize the GmailClient, load or obtain OAuth credentials, prepare label cache and lock, and resolve the authenticated user's email address.
        
        Parameters:
            credentials_path (str): Path to the OAuth client secrets JSON used to run an authorization flow if no valid token is available. Default: 'credentials.json'.
            token_path (str): Path to the stored OAuth token JSON used to load persisted credentials and to persist refreshed/obtained tokens. Default: 'token.json'.
        
        Notes:
            This constructor loads credentials (which may refresh or trigger an OAuth flow) and sets up thread-local state for the Gmail API client, a protected label cache, and the authenticated user's email address.
        """
        self.credentials_path = credentials_path
        self.token_path = token_path
        self._creds = self._load_credentials()
        self._labels_cache = None
        self._labels_lock = threading.Lock()
        self.email_address = self._get_user_email()

    def _get_user_email(self):
        """
        Obtain the authenticated user's email address.
        
        Returns:
            email (str): The authenticated user's email address, or "unknown" if the profile cannot be retrieved.
        """
        try:
            profile = self.service.users().getProfile(userId='me').execute()
            return profile.get('emailAddress')
        except Exception as e:
            logging.error(f"Error fetching user profile: {e}")
            return "unknown"

    def _load_credentials(self):
        """
        Load or obtain OAuth2 credentials for the Gmail API and persist them to the configured token path.
        
        Attempts to load credentials from the client's token file, then from an environment variable containing token JSON. If loaded credentials are expired and can be refreshed, refreshes them; otherwise runs a local OAuth flow using the configured credentials file. Writes obtained or refreshed credentials to the token path before returning.
        
        Returns:
            creds (google.auth.credentials.Credentials): Valid credentials authorized for the Gmail scopes.
        
        Raises:
            FileNotFoundError: If no valid credentials are available and the client credentials file does not exist.
        """
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
        """
        Provide a thread-local Gmail API service client for the authenticated user.
        
        Returns:
            service: The Gmail API service client instance bound to the current thread.
        """
        if not hasattr(self._thread_local, "service"):
            self._thread_local.service = build('gmail', 'v1', credentials=self._creds)
        return self._thread_local.service

    def _get_labels(self):
        """
        Provide a thread-safe mapping of Gmail label names to their IDs, populating the cache if needed.
        
        Returns:
            dict: Mapping from label name (str) to label ID (str).
        """
        with self._labels_lock:
            if self._labels_cache is None:
                results = self.service.users().labels().list(userId='me').execute()
                labels = results.get('labels', [])
                self._labels_cache = {label['name']: label['id'] for label in labels}
        return self._labels_cache

    @retry_with_backoff()
    def list_unread_messages(self, user_id='me'):
        """
        List all unread message references for the given user.
        
        Invalidates the client's label cache, then pages through the Gmail API collecting unread message references until all pages are retrieved.
        
        Returns:
            list: A list of message reference dictionaries as returned by the Gmail API (each typically contains keys such as `id` and `threadId`).
        """
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
        """
        Retrieve a Gmail message resource by its message ID.
        
        Parameters:
            message_id (str): The ID of the message to fetch.
            user_id (str): User's email address or the special value `'me'` for the authenticated user.
        
        Returns:
            dict: The Gmail API message resource as returned by the API.
        """
        return self.service.users().messages().get(userId=user_id, id=message_id).execute()

    @retry_with_backoff()
    def mark_as_read(self, message_id, user_id='me'):
        """
        Mark a Gmail message as read by removing the 'UNREAD' label.
        
        Parameters:
            message_id (str): ID of the Gmail message to mark as read.
            user_id (str): User's email address or the special value 'me' for the authenticated user.
        
        Returns:
            dict: The Gmail API response from the `messages.batchModify().execute()` call.
        """
        return self.service.users().messages().batchModify(
            userId=user_id,
            body={
                'ids': [message_id],
                'removeLabelIds': ['UNREAD']
            }
        ).execute()

    @retry_with_backoff()
    def move_to_trash(self, message_id, user_id='me'):
        """
        Move a Gmail message to the user's Trash.
        
        Parameters:
            message_id (str): The ID of the message to move to trash.
            user_id (str): The user identifier. Use 'me' to indicate the authenticated user.
        
        Returns:
            dict: The Gmail API response for the trash operation.
        """
        return self.service.users().messages().trash(userId=user_id, id=message_id).execute()

    @retry_with_backoff()
    def apply_labels(self, message_id, label_ids, user_id='me'):
        """
        Apply the specified labels to a Gmail message, creating missing custom labels as needed.
        
        Parameters:
            message_id (str): The ID of the message to label.
            label_ids (Iterable[str]): Iterable of label names or system label identifiers to apply.
                - If an entry matches an existing custom label name, its corresponding label ID is used.
                - If an entry is a known Gmail system label (e.g., 'INBOX', 'UNREAD', 'SPAM', 'TRASH', 'STARRED', 'IMPORTANT', 'SENT', 'DRAFT', 'CATEGORY_PERSONAL', 'CATEGORY_SOCIAL', 'CATEGORY_PROMOTIONS', 'CATEGORY_UPDATES', 'CATEGORY_FORUMS'), it is passed through as-is.
                - Otherwise a new custom label is created; on success its ID is used and the local label cache is updated. Failures to create a label are logged and that label is omitted.
            user_id (str): The user identifier for the Gmail API call (default 'me').
        
        Returns:
            dict or None: The Gmail API response from `messages().batchModify(...).execute()` if any labels were applied; `None` if no labels were resolved to apply.
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

        return self.service.users().messages().batchModify(
            userId=user_id,
            body={
                'ids': [message_id],
                'addLabelIds': final_label_ids
            }
        ).execute()
