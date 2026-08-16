import datetime
import os
import threading


class RequestStore:
    def __init__(self, data_dir: str, max_hashes: int = 10000):
        self.data_dir = os.path.abspath(data_dir)
        self.max_hashes = max_hashes
        self.last_filename = ""
        self._hashes = set()
        self._lock = threading.Lock()

    def save_message(self, text: str) -> str:
        try:
            os.makedirs(self.data_dir, exist_ok=True)
            fname = datetime.datetime.now().strftime("received_%Y%m%d_%H%M%S") + ".txt"
            with open(os.path.join(self.data_dir, fname), "w", encoding="utf-8") as f:
                f.write(text)
            self.last_filename = fname
            return fname
        except Exception as e:
            print(f"[ios-deposit] 저장 오류: {e}")
            return ""

    def append_log(self, result_type: str, detail: str = ""):
        try:
            os.makedirs(self.data_dir, exist_ok=True)
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            parts = [ts, result_type]
            if detail:
                parts.append(detail)
            if self.last_filename:
                parts.append(self.last_filename)
            with open(os.path.join(self.data_dir, "request_log.txt"), "a", encoding="utf-8") as f:
                f.write(" | ".join(parts) + "\n")
        except Exception:
            pass

    def is_duplicate(self, msg_hash: str) -> bool:
        with self._lock:
            if msg_hash in self._hashes:
                return True
            self._hashes.add(msg_hash)
            return False

    def trim_hashes(self):
        with self._lock:
            while len(self._hashes) > self.max_hashes and self._hashes:
                self._hashes.discard(next(iter(self._hashes)))
