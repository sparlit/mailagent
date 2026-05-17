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
    Create a decorator that retries a function on transient Gmail API `HttpError` responses using exponential backoff with jitter.
    
    Parameters:
        max_retries (int): Maximum number of retry attempts before performing one final call without further backoff (default 5).
    
    Returns:
        decorator (callable): A decorator that, when applied to a function, retries the call when a caught `googleapiclient.errors.HttpError` has an HTTP status of 429, 500, 502, 503, or 504. Non-retryable `HttpError` statuses are re-raised immediately.
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
        Initialize the GmailClient, loading OAuth credentials and preparing internal state.
        
        Parameters:
            credentials_path (str): Path to the OAuth client secrets JSON used to perform an OAuth flow if no valid saved credentials exist.
            token_path (str): Path to the JSON file used to load and persist the user's access/refresh token; also checked via an environment-variable fallback.
            
        The constructor loads or refreshes credentials, initializes the label cache and its lock, and retrieves the authenticated user's email address.
        """
        self.credentials_path = credentials_path
        self.token_path = token_path
        self._creds = self._load_credentials()
        self._labels_cache = None
        self._labels_lock = threading.Lock()
        self.email_address = self._get_user_email()

    def _get_user_email(self):
        """
        Retrieve the authenticated user's primary Gmail address.
        
        Returns:
            str: The user's email address, or "unknown" if the profile could not be retrieved.
        """
        try:
            profile = self.service.users().getProfile(userId='me').execute()
            return profile.get('emailAddress')
        except Exception as e:
            logging.error(f"Error fetching user profile: {e}")
            return "unknown"

    def _load_credentials(self):
        """
        Load and return OAuth2 credentials for the Gmail API using available sources.
        
        Attempts to load credentials from the instance's token file. If not present, checks an environment variable named
        `GMAIL_TOKEN_<TOKEN_BASENAME>` (token file basename uppercased with dots replaced by underscores) and loads credentials
        from its JSON payload. If loaded credentials are expired and contain a refresh token, refreshes them. Otherwise, initiates
        an OAuth local server flow using the instance's credentials file and persists the obtained credentials to the token file.
        Raises FileNotFoundError when a local OAuth flow is required but the credentials file does not exist.
        
        Returns:
            Credentials: An authorized `google.auth.credentials.Credentials` instance.
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
        Provide a thread-local Gmail API client instance.
        
        Returns:
            gmail_service (googleapiclient.discovery.Resource): The cached per-thread Gmail API service built with the client's credentials.
        """
        if not hasattr(self._thread_local, "service"):
            self._thread_local.service = build('gmail', 'v1', credentials=self._creds)
        return self._thread_local.service

    def _get_labels(self):
        """
        Return a thread-safe cached mapping of Gmail label names to their label IDs, populating the cache from the Gmail API if not already set.
        
        This method acquires an internal lock to ensure only one thread populates the cache when it is empty.
        
        Returns:
            dict: Mapping where keys are label names (str) and values are label IDs (str).
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
        Retrieve all unread Gmail messages for the specified user and clear the internal label cache.
        
        This method clears the client's label cache as a side effect, then fetches all messages matching `is:unread`, handling pagination until all pages are retrieved.
        
        Returns:
            list: Message resource objects as returned by the Gmail API; each object typically includes at least `id` and `threadId`.
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
        Retrieve a Gmail message resource by message ID.
        
        Parameters:
            message_id (str): The Gmail message ID to fetch.
            user_id (str): User's email address or the special value `'me'` (default `'me'`).
        
        Returns:
            dict: The Gmail message resource as returned by the Gmail API, including headers, body payload, labels, and metadata.
        """
        return self.service.users().messages().get(userId=user_id, id=message_id).execute()

    @retry_with_backoff()
    def mark_as_read(self, message_id, user_id='me'):
        """
        Mark a Gmail message as read by removing the 'UNREAD' label.
        
        Parameters:
            message_id (str): The Gmail message ID to mark as read.
            user_id (str): The user's email address or the special value 'me' (default 'me').
        
        Returns:
            dict: The Gmail API response from the batchModify call.
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
        Move the specified message to the user's Trash.
        
        Parameters:
            message_id (str): ID of the message to move.
            user_id (str): User's email address or the literal `'me'` for the authenticated user.
        
        Returns:
            result (dict): Response returned by the Gmail API `messages.trash` method.
        """
        return self.service.users().messages().trash(userId=user_id, id=message_id).execute()

    @retry_with_backoff()
    def apply_labels(self, message_id, label_ids, user_id='me'):
        """
        Apply the given labels to a Gmail message, creating any missing custom labels.
        
        Parameters:
            message_id (str): The ID of the message to modify.
            label_ids (list[str]): Label names or IDs to apply. Known system/category labels (e.g. 'INBOX', 'SPAM', 'UNREAD', 'CATEGORY_PROMOTIONS') are accepted as-is; other names will be created if missing.
            user_id (str): User identifier for the Gmail API (defaults to 'me').
        
        Returns:
            dict or None: The Gmail API response from `messages.batchModify` when labels were applied, or `None` if no labels were resolved/applied.
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
