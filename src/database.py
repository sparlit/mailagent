import sqlite3
import threading

__all__ = ['Database']

class Database:
    def __init__(self, db_path='processed_messages.db'):
        """
        Initialize the Database instance.

        Parameters:
            db_path (str): The path to the SQLite database file. Use ':memory:' for transient in-memory databases.
        """
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _get_connection(self):
        """
        Helper to get a thread-safe connection, handling :memory: for tests.

        Returns:
            sqlite3.Connection: A connection to the database.
        """
        if self.db_path == ':memory:':
            if not hasattr(self, '_memory_conn'):
                self._memory_conn = sqlite3.connect(':memory:', check_same_thread=False)
            return self._memory_conn
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """
        Ensure the SQLite database at self.db_path contains the required schema for the application.
        
        Creates the `processed_messages`, `stats`, and `activity_log` tables if they do not exist.
        """
        with self._lock:
            conn = self._get_connection()
            try:
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
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS activity_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        account_email TEXT,
                        message_id TEXT,
                        action TEXT,
                        category TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                conn.commit()
            finally:
                if self.db_path != ':memory:':
                    conn.close()

    def is_processed(self, message_id, account_email):
        """
        Determine whether a specific message has already been recorded as processed for the given account.
        
        Parameters:
            message_id (str): The unique identifier of the message to check.
            account_email (str): The account email associated with the message.
        
        Returns:
            bool: True if a record exists for the given message_id and account_email, False otherwise.
        """
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.execute(
                    'SELECT 1 FROM processed_messages WHERE message_id = ? AND account_email = ?',
                    (message_id, account_email)
                )
                return cursor.fetchone() is not None
            finally:
                if self.db_path != ':memory:':
                    conn.close()

    def mark_as_processed(self, message_id, account_email):
        """
        Record a message as processed in the database.

        Parameters:
            message_id (str): The message identifier.
            account_email (str): The account email.
        """
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute(
                    'INSERT OR IGNORE INTO processed_messages (message_id, account_email) VALUES (?, ?)',
                    (message_id, account_email)
                )
                conn.commit()
            finally:
                if self.db_path != ':memory:':
                    conn.close()

    def record_stat(self, account_email, action, category):
        """
        Increment the count for a specific action/category combination in the stats table.

        Parameters:
            account_email (str): The account email.
            action (str): The action performed.
            category (str): The classification category.
        """
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute('''
                    INSERT INTO stats (account_email, action, category, count)
                    VALUES (?, ?, ?, 1)
                    ON CONFLICT(account_email, action, category) DO UPDATE SET count = count + 1
                ''', (account_email, action, category))
                conn.commit()
            finally:
                if self.db_path != ':memory:':
                    conn.close()

    def get_stats(self):
        """
        Retrieve all action statistics from the database.

        Returns:
            list[tuple]: List of (account_email, action, category, count) tuples.
        """
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.execute('SELECT account_email, action, category, count FROM stats')
                return cursor.fetchall()
            finally:
                if self.db_path != ':memory:':
                    conn.close()

    def log_activity(self, account_email, message_id, action, category):
        """
        Log an action performed on a message to the activity_log table.

        Parameters:
            account_email (str): The account email.
            message_id (str): The message identifier.
            action (str): The action performed.
            category (str): The classification category.
        """
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute('''
                    INSERT INTO activity_log (account_email, message_id, action, category)
                    VALUES (?, ?, ?, ?)
                ''', (account_email, message_id, action, category))
                conn.commit()
            finally:
                if self.db_path != ':memory:':
                    conn.close()

    def record_activity(self, account_email, message_id, action, category):
        """Alias for log_activity to maintain backward compatibility."""
        self.log_activity(account_email, message_id, action, category)

    def get_recent_activity(self, limit=10):
        """
        Retrieve the most recent logged activities.

        Parameters:
            limit (int): Maximum number of records to return.

        Returns:
            list[tuple]: List of (account_email, message_id, action, category, timestamp) tuples.
        """
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.execute('''
                    SELECT account_email, message_id, action, category, timestamp
                    FROM activity_log
                    ORDER BY id DESC
                    LIMIT ?
                ''', (limit,))
                return cursor.fetchall()
            finally:
                if self.db_path != ':memory:':
                    conn.close()

    def cleanup_old_data(self, days=30):
        """
        Remove activity log and processed message entries older than the specified number of days.

        Parameters:
            days (int): Retention period in days.
        """
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute("DELETE FROM activity_log WHERE timestamp < datetime('now', '-' || ? || ' days')", (days,))
                conn.execute("DELETE FROM processed_messages WHERE processed_at < datetime('now', '-' || ? || ' days')", (days,))
                conn.commit()
            finally:
                if self.db_path != ':memory:':
                    conn.close()
