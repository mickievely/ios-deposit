"""웹 자판기 / 쇼핑몰이 입금 웹훅을 받는 예시.

ios-deposit 의 webhook_url 에
  http://127.0.0.1:5000/api/charge/sms
를 넣으면 여기로 들어옵니다.
"""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer


class WebVendingHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _send(self, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path.split("?", 1)[0] != "/api/charge/sms":
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        parsed = data.get("parsed") or {}
        amount = parsed.get("amount")
        depositor = parsed.get("depositor")

        print(f"[웹자판기] 입금 {amount}원 / {depositor}")
        # 여기서 대기 주문 매칭, 재화 지급, DB 업데이트 하면 됨
        self._send({"ok": True, "matched": True})


if __name__ == "__main__":
    print("웹 수신 예시  http://127.0.0.1:5000/api/charge/sms")
    HTTPServer(("127.0.0.1", 5000), WebVendingHandler).serve_forever()
