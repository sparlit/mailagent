import os
import json
import unittest
from unittest.mock import patch, MagicMock
from src.gmail_client import GmailClient

class TestCredentialsEnv(unittest.TestCase):
    def setUp(self):
        self.credentials_content = {
            "installed": {
                "client_id": "fake_id",
                "project_id": "fake_project",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_secret": "fake_secret",
                "redirect_uris": ["http://localhost"]
            }
        }
        self.token_content = {
            "token": "fake_token",
            "refresh_token": "fake_refresh_token",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "fake_id",
            "client_secret": "fake_secret",
            "scopes": ["https://www.googleapis.com/auth/gmail.modify"],
            "expiry": "2099-01-01T00:00:00Z"
        }

    @patch('src.gmail_client.Credentials')
    @patch('src.gmail_client.build')
    @patch('src.gmail_client.InstalledAppFlow')
    @patch('os.path.exists')
    def test_load_credentials_from_env(self, mock_exists, mock_flow_class, mock_build, mock_creds_class):
        # Setup mocks
        mock_exists.return_value = False # No files exist

        # Mock credentials object returned by Credentials.from_authorized_user_info
        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_creds_class.from_authorized_user_info.return_value = mock_creds

        # Mock flow object
        mock_flow = MagicMock()
        mock_flow_class.from_client_config.return_value = mock_flow
        mock_flow.run_local_server.return_value = mock_creds

        # Set environment variables
        os.environ['GMAIL_CREDENTIALS_CREDENTIALS_JSON'] = json.dumps(self.credentials_content)
        os.environ['GMAIL_TOKEN_TOKEN_JSON'] = json.dumps(self.token_content)

        try:
            # Initialize client
            # It will first try to load token from env, which should succeed.
            with patch('builtins.open', unittest.mock.mock_open()):
                client = GmailClient(credentials_path='credentials.json', token_path='token.json')

            # Verify that Credentials.from_authorized_user_info was called with token data
            mock_creds_class.from_authorized_user_info.assert_called_once()
            args, kwargs = mock_creds_class.from_authorized_user_info.call_args
            self.assertEqual(args[0], self.token_content)

        finally:
            # Clean up
            if 'GMAIL_CREDENTIALS_CREDENTIALS_JSON' in os.environ:
                del os.environ['GMAIL_CREDENTIALS_CREDENTIALS_JSON']
            if 'GMAIL_TOKEN_TOKEN_JSON' in os.environ:
                del os.environ['GMAIL_TOKEN_TOKEN_JSON']

    @patch('src.gmail_client.Credentials')
    @patch('src.gmail_client.build')
    @patch('src.gmail_client.InstalledAppFlow')
    @patch('os.path.exists')
    def test_load_credentials_fallback_to_env_when_token_missing(self, mock_exists, mock_flow_class, mock_build, mock_creds_class):
        # Setup mocks
        mock_exists.return_value = False # No files exist

        mock_creds = MagicMock()
        mock_creds.valid = True

        # Mock flow
        mock_flow = MagicMock()
        mock_flow_class.from_client_config.return_value = mock_flow
        mock_flow.run_local_server.return_value = mock_creds

        # Set environment variable for credentials only
        os.environ['GMAIL_CREDENTIALS_CREDENTIALS_JSON'] = json.dumps(self.credentials_content)

        if 'GMAIL_TOKEN_TOKEN_JSON' in os.environ:
            del os.environ['GMAIL_TOKEN_TOKEN_JSON']

        try:
            with patch('builtins.open', unittest.mock.mock_open()):
                client = GmailClient(credentials_path='credentials.json', token_path='token.json')

            # Verify that InstalledAppFlow.from_client_config was called with credentials data
            mock_flow_class.from_client_config.assert_called_once()
            args, kwargs = mock_flow_class.from_client_config.call_args
            self.assertEqual(args[0], self.credentials_content)

        finally:
            if 'GMAIL_CREDENTIALS_CREDENTIALS_JSON' in os.environ:
                del os.environ['GMAIL_CREDENTIALS_CREDENTIALS_JSON']

if __name__ == '__main__':
    unittest.main()
