import unittest
from unittest.mock import MagicMock, patch
from src.gmail_client import GmailClient

class TestGmailClient(unittest.TestCase):
    @patch('src.gmail_client.Credentials')
    @patch('src.gmail_client.build')
    @patch('src.gmail_client.GmailClient._get_user_email')
    @patch('os.path.exists')
    def setUp(self, mock_exists, mock_get_email, mock_build, mock_creds):
        mock_exists.return_value = True
        mock_get_email.return_value = "test@example.com"
        mock_creds.from_authorized_user_file.return_value = MagicMock()
        self.client = GmailClient(credentials_path='fake_creds.json', token_path='fake_token.json')
        self.client._thread_local.service = MagicMock()

    def test_archive(self):
        msg_id = 'msg123'
        self.client.archive(msg_id)
        self.client.service.users().messages().batchModify.assert_called_once_with(
            userId='me',
            body={
                'ids': [msg_id],
                'removeLabelIds': ['INBOX']
            }
        )

    def test_star(self):
        msg_id = 'msg123'
        self.client.star(msg_id)
        self.client.service.users().messages().batchModify.assert_called_once_with(
            userId='me',
            body={
                'ids': [msg_id],
                'addLabelIds': ['STARRED']
            }
        )

    def test_unstar(self):
        msg_id = 'msg123'
        self.client.unstar(msg_id)
        self.client.service.users().messages().batchModify.assert_called_once_with(
            userId='me',
            body={
                'ids': [msg_id],
                'removeLabelIds': ['STARRED']
            }
        )

    def test_mark_important(self):
        msg_id = 'msg123'
        self.client.mark_important(msg_id)
        self.client.service.users().messages().batchModify.assert_called_once_with(
            userId='me',
            body={
                'ids': [msg_id],
                'addLabelIds': ['IMPORTANT']
            }
        )

if __name__ == '__main__':
    unittest.main()
