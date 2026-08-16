import os
import sqlite3
import threading
from datetime import datetime
from typing import Optional


DB_NAME = "ios_deposit.db"


class RequestStore:
    def __init__(self, data_dir: str):
        self.data_dir = os.path.abspath(data_dir)
        self.db_path = os.path.join(self.data_dir, DB_NAME)
        self._lock = threading.Lock()
        self._conn = None
        os.makedirs(self.data_dir, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        if self._conn is not None:
            return self._conn
        conn = sqlite3.connect(self.db_path, timeout=10, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
        self._conn = conn
        return conn

    def _init_db(self):
        with self._lock:
            conn = self._connect()
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS deposits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    received_at TEXT NOT NULL,
                    message TEXT NOT NULL,
                    msg_hash TEXT NOT NULL,
                    result TEXT NOT NULL,
                    detail TEXT,
                    amount INTEGER,
                    depositor TEXT,
                    user_id TEXT
                );
                CREATE TABLE IF NOT EXISTS seen_hashes (
                    msg_hash TEXT PRIMARY KEY,
                    first_seen TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_deposits_hash ON deposits(msg_hash);
                CREATE INDEX IF NOT EXISTS idx_deposits_received ON deposits(received_at);
                INSERT OR IGNORE INTO seen_hashes (msg_hash, first_seen)
                SELECT msg_hash, MIN(received_at) FROM deposits GROUP BY msg_hash;
                """
            )
            conn.commit()

    def claim(self, msg_hash: str) -> bool:
        now = datetime.now().isoformat(timespec="seconds")
        with self._lock:
            conn = self._connect()
            cur = conn.execute(
                "INSERT OR IGNORE INTO seen_hashes (msg_hash, first_seen) VALUES (?, ?)",
                (msg_hash, now),
            )
            conn.commit()
            return cur.rowcount == 1

    def record(
        self,
        *,
        message: str,
        msg_hash: str,
        result: str,
        detail: str = "",
        parsed: Optional[dict] = None,
        user_id=None,
    ) -> None:
        amount = None
        depositor = None
        if parsed:
            amount = parsed.get("amount")
            depositor = parsed.get("depositor")
        uid = "" if user_id is None else str(user_id)
        try:
            with self._lock:
                conn = self._connect()
                conn.execute(
                    """
                    INSERT INTO deposits (
                        received_at, message, msg_hash, result, detail,
                        amount, depositor, user_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        datetime.now().isoformat(timespec="seconds"),
                        message,
                        msg_hash,
                        result,
                        detail or "",
                        amount,
                        depositor,
                        uid,
                    ),
                )
                conn.commit()
        except Exception as e:
            print(f"[ios-deposit] 저장 오류: {e}")
