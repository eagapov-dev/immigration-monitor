"""
Database module for tracking processed posts/messages.
Prevents duplicate notifications.
"""
import sqlite3
import os
from datetime import datetime, timedelta
from typing import Optional


class Database:
    def __init__(self, db_path: str = "data/processed.db"):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self._create_tables()

    def _create_tables(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS processed_items (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,        -- 'reddit_post', 'reddit_comment', 'telegram'
                group_name TEXT,
                text_preview TEXT,
                url TEXT,
                classification TEXT,          -- JSON string with category, urgency etc
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notified BOOLEAN DEFAULT 0
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS notification_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id TEXT,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_processed_at 
            ON processed_items(processed_at)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_source 
            ON processed_items(source)
        """)
        self.conn.commit()

    def is_processed(self, item_id: str) -> bool:
        """Check if an item has already been processed."""
        cursor = self.conn.execute(
            "SELECT 1 FROM processed_items WHERE id = ?", (item_id,)
        )
        return cursor.fetchone() is not None

    def mark_processed(
        self,
        item_id: str,
        source: str,
        group_name: str,
        text_preview: str,
        url: str,
        classification: Optional[str] = None,
    ):
        """Mark an item as processed."""
        self.conn.execute(
            """INSERT OR IGNORE INTO processed_items 
               (id, source, group_name, text_preview, url, classification) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            (item_id, source, group_name, text_preview[:500], url, classification),
        )
        self.conn.commit()

    def mark_notified(self, item_id: str):
        """Mark an item as notified (sent to Telegram)."""
        self.conn.execute(
            "UPDATE processed_items SET notified = 1 WHERE id = ?", (item_id,)
        )
        self.conn.execute(
            "INSERT INTO notification_log (item_id) VALUES (?)", (item_id,)
        )
        self.conn.commit()

    def get_notifications_count_last_hour(self) -> int:
        """Get count of notifications sent in the last hour."""
        hour_ago = datetime.utcnow() - timedelta(hours=1)
        cursor = self.conn.execute(
            "SELECT COUNT(*) FROM notification_log WHERE sent_at > ?",
            (hour_ago.isoformat(),),
        )
        return cursor.fetchone()[0]

    def cleanup_old_records(self, days: int = 30):
        """Remove records older than specified days."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        self.conn.execute(
            "DELETE FROM processed_items WHERE processed_at < ?",
            (cutoff.isoformat(),),
        )
        self.conn.execute(
            "DELETE FROM notification_log WHERE sent_at < ?",
            (cutoff.isoformat(),),
        )
        self.conn.commit()

    def get_stats(self) -> dict:
        """Get processing statistics."""
        stats = {}
        cursor = self.conn.execute("SELECT COUNT(*) FROM processed_items")
        stats["total_processed"] = cursor.fetchone()[0]

        cursor = self.conn.execute(
            "SELECT COUNT(*) FROM processed_items WHERE notified = 1"
        )
        stats["total_notified"] = cursor.fetchone()[0]

        cursor = self.conn.execute(
            "SELECT source, COUNT(*) FROM processed_items GROUP BY source"
        )
        stats["by_source"] = dict(cursor.fetchall())

        today = datetime.utcnow().strftime("%Y-%m-%d")
        cursor = self.conn.execute(
            "SELECT COUNT(*) FROM processed_items WHERE processed_at >= ?",
            (today,),
        )
        stats["today_processed"] = cursor.fetchone()[0]

        return stats

    def close(self):
        self.conn.close()
