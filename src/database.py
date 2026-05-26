import sqlite3
import threading

__all__ = ['Database']

class Database:
    def __init__(self, db_path='processed_messages.db'):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        """
        Ensure the SQLite database at self.db_path contains the required schema for the application.
        
        Creates the `processed_messages` table (columns: `message_id`, `account_email`, `processed_at` with a default of the current timestamp) with a composite primary key on `(message_id, account_email)`, and the `stats` table (columns: `account_email`, `action`, `category`, `count` with default 0) with a composite primary key on `(account_email, action, category)`. The operation is performed under the instance lock and commits any schema changes.
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

    def is_processed(self, message_id, account_email):
        """
        Determine whether a specific message has already been recorded as processed for the given account.
        
        Parameters:
            message_id (str): The unique identifier of the message to check.
            account_email (str): The account email associated with the message.
        
        Returns:
            True if a record exists for the given message_id and account_email, False otherwise.
        """
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    'SELECT 1 FROM processed_messages WHERE message_id = ? AND account_email = ?',
                    (message_id, account_email)
                )
                return cursor.fetchone() is not None

    def mark_as_processed(self, message_id, account_email):
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    'INSERT OR IGNORE INTO processed_messages (message_id, account_email) VALUES (?, ?)',
                    (message_id, account_email)
                )
                conn.commit()

    def record_stat(self, account_email, action, category):
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT INTO stats (account_email, action, category, count)
                    VALUES (?, ?, ?, 1)
                    ON CONFLICT(account_email, action, category) DO UPDATE SET count = count + 1
                ''', (account_email, action, category))
                conn.commit()

    def get_stats(self):
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('SELECT account_email, action, category, count FROM stats')
                return cursor.fetchall()

    def log_activity(self, account_email, message_id, action, category):
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT INTO activity_log (account_email, message_id, action, category)
                    VALUES (?, ?, ?, ?)
                ''', (account_email, message_id, action, category))
                conn.commit()

    def get_recent_activity(self, limit=10):
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    SELECT account_email, message_id, action, category, timestamp
                    FROM activity_log
                    ORDER BY timestamp DESC LIMIT ?
                ''', (limit,))
                return cursor.fetchall()

    def cleanup_old_data(self, days=30):
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM activity_log WHERE timestamp < datetime('now', '-' || ? || ' days')", (days,))
                conn.execute("DELETE FROM processed_messages WHERE processed_at < datetime('now', '-' || ? || ' days')", (days,))
                conn.commit()
