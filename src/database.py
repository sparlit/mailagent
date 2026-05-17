import sqlite3
import threading

class Database:
    def __init__(self, db_path='processed_messages.db'):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
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
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    'SELECT 1 FROM processed_messages WHERE message_id = ?',
                    (message_id,)
                )
                return cursor.fetchone() is not None

    def mark_as_processed(self, message_id, account_email=None):
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
