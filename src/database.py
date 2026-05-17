import sqlite3
import threading

class Database:
    def __init__(self, db_path='processed_messages.db'):
        """
        Initialize the Database instance, set the SQLite file path, create a thread lock for serialized access, and ensure required tables exist.
        
        Parameters:
            db_path (str): Path to the SQLite database file used to persist processed message IDs and aggregated stats. Defaults to 'processed_messages.db'.
        """
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        """
        Ensure the database schema exists by creating required tables if they are missing.
        
        Creates two tables in the configured SQLite database file:
        - processed_messages: columns `message_id` (TEXT, primary key), `account_email` (TEXT), `processed_at` (TIMESTAMP, defaults to CURRENT_TIMESTAMP).
        - stats: columns `account_email` (TEXT), `action` (TEXT), `category` (TEXT), `count` (INTEGER, defaults to 0); primary key is the composite `(account_email, action, category)`.
        
        This operation is idempotent and persists changes to the database.
        """
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS processed_messages (
                        message_id TEXT PRIMARY KEY,
                        account_email TEXT,
                        processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS stats (
                        account_email TEXT,
                        action TEXT,
                        category TEXT,
                        count INTEGER DEFAULT 0,
                        PRIMARY KEY (account_email, action, category)
                    )
                ''')
                conn.commit()

    def is_processed(self, message_id):
        """
        Check whether a message ID has already been recorded as processed.
        
        Parameters:
            message_id (str): Identifier of the message to check.
        
        Returns:
            True if the message_id exists in the processed messages table, False otherwise.
        """
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    'SELECT 1 FROM processed_messages WHERE message_id = ?',
                    (message_id,)
                )
                return cursor.fetchone() is not None

    def mark_as_processed(self, message_id, account_email=None):
        """
        Record a message ID as processed by inserting it into the persistent store.
        
        Inserts a row into the `processed_messages` table mapping `message_id` to `account_email`. If a row with the same `message_id` already exists, the insert is ignored and the existing row is left unchanged.
        
        Parameters:
            message_id (str): Unique identifier of the message to mark as processed.
            account_email (str | None): Optional email of the account associated with the message; stored alongside the message ID.
        """
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    'INSERT OR IGNORE INTO processed_messages (message_id, account_email) VALUES (?, ?)',
                    (message_id, account_email)
                )
                conn.commit()

    def record_stat(self, account_email, action, category):
        """
        Increment the counter for the specified account, action, and category in the stats table.
        
        If a matching row does not exist, insert one with count = 1; if it does exist, increment its count by 1.
        
        Parameters:
            account_email (str): Email address of the account associated with the stat.
            action (str): Action name to record (e.g., "processed", "sent").
            category (str): Category label for the stat (e.g., "inbound", "spam").
        """
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT INTO stats (account_email, action, category, count)
                    VALUES (?, ?, ?, 1)
                    ON CONFLICT(account_email, action, category) DO UPDATE SET count = count + 1
                ''', (account_email, action, category))
                conn.commit()

    def get_stats(self):
        """
        Return all stored statistics rows from the database.
        
        Each row is a tuple (account_email, action, category, count) representing the aggregated count for that account/action/category as stored in the `stats` table.
        
        Returns:
            list[tuple[str, str, str, int]]: All rows from `stats` in the form (account_email, action, category, count).
        """
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('SELECT account_email, action, category, count FROM stats')
                return cursor.fetchall()
