"""자판기 봇이나 직접 핸들러에 붙이는 예시. 실행용이 아니라 참고용입니다."""

import asyncio
import threading

from ios_deposit import run_ios_deposit_api_server, start_ios_charge_api_server_thread


async def process_charge_message_content(content: str, reply_channel=None):
    if not content or not content.strip():
        return False, None, None
    print(f"[예시] 입금 문자 처리: {content[:120]}")
    return False, None, None


class FakeBot:
    def __init__(self):
        self.loop = asyncio.get_event_loop()
        self._charge_api_loop = self.loop


def example_embed_in_bot():
    bot = FakeBot()

    def run_legacy():
        run_ios_deposit_api_server(bot, process_charge_message_content)

    threading.Thread(target=run_legacy, daemon=True).start()
    print("기존 자판기 방식 — bot + process_charge_message_content (:88)")


def example_custom_handler():
    async def my_handler(message: str, reply_channel=None):
        print("받은 문자:", message[:100])
        return False, None, ""

    start_ios_charge_api_server_thread(
        my_handler,
        port=8088,
        loop=asyncio.get_event_loop(),
    )
    print("커스텀 핸들러 — :8088")


if __name__ == "__main__":
    print("examples/integrate_bot.py 는 참고용입니다.")
    print("1) example_embed_in_bot — 자판기 봇에 그대로 붙이기")
    print("2) example_custom_handler — async 함수 직접 연결")
    print("3) app.py — webhook_url 로 다른 서버에 전달")
