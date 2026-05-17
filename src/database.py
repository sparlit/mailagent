import sqlite3
import threading

class Database:
    def __init__(self, db_path='processed_messages.db'):
        """
        Initialize the Database instance and ensure required SQLite tables exist.
        
        Parameters:
            db_path (str): Filesystem path to the SQLite database file. Defaults to 'processed_messages.db'.
        
        Description:
            Stores the database path, creates an internal threading lock for serializing access, and initializes the database schema (creating required tables if they do not exist).
        """
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        """
        Initialize the SQLite database schema used by this Database instance.
        
        Creates the tables `processed_messages` and `stats` if they do not already exist:
        - `processed_messages`: columns `message_id`, `account_email`, `processed_at` (defaults to current timestamp); composite primary key `(message_id, account_email)`.
        - `stats`: columns `account_email`, `action`, `category`, `count` (defaults to 0); composite primary key `(account_email, action, category)`.
        
        Acquires the instance lock to serialize database access and persists the schema changes.
        """
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS processed_messages (
                        message_id TEXT,
                        account_email TEXT,
                        processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (message_id, account_email)
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

    def is_processed(self, message_id, account_email):
        """
        Check whether a message for an account has already been recorded as processed.
        
        Parameters:
            message_id (str): Unique identifier of the message.
            account_email (str): Email address of the account associated with the message.
        
        Returns:
            bool: `True` if a record exists for the given `message_id` and `account_email`, `False` otherwise.
        """
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    'SELECT 1 FROM processed_messages WHERE message_id = ? AND account_email = ?',
                    (message_id, account_email)
                )
                return cursor.fetchone() is not None

    def mark_as_processed(self, message_id, account_email):
        """
        Record that a message has been processed for a specific account.
        
        Inserts the (message_id, account_email) pair into the processed_messages table; if the pair already exists the operation is ignored, making the call idempotent.
        
        Parameters:
            message_id (str): Unique identifier of the message.
            account_email (str): Email of the account that processed the message.
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
        Increment the stored counter for a given account/action/category, creating the row with count 1 if it does not exist.
        
        Parameters:
            account_email (str): Email identifying the account whose stat to increment.
            action (str): Name of the action to record.
            category (str): Category or label for the action.
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
        Return all aggregated statistic rows from the stats table.
        
        Returns:
            list[tuple]: A list of tuples (account_email, action, category, count) where `account_email`, `action`, and `category` are strings and `count` is an integer.
        """
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('SELECT account_email, action, category, count FROM stats')
                return cursor.fetchall()
