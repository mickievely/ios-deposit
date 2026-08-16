import socket
import threading
from http.server import HTTPServer
from socketserver import ThreadingMixIn
from typing import Any, Callable

from ios_deposit.config.settings import Settings
from ios_deposit.handler import resolve_loop
from ios_deposit.parse.deposit import parse_deposit_message
from ios_deposit.router.http import build_charge_api_handler


class ChargeHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    block_on_close = False

    def __init__(self, server_address, RequestHandlerClass, queue_size: int = 64):
        self.request_queue_size = max(8, int(queue_size))
        super().__init__(server_address, RequestHandlerClass)

    def finish_request(self, request, client_address):
        try:
            request.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError:
            pass
        super().finish_request(request, client_address)


__version__ = "0.1.3"

__all__ = [
    "attach",
    "attach_bot",
    "parse_deposit_message",
    "run_ios_deposit_api_server",
    "start_ios_charge_api_server",
    "start_ios_charge_api_server_thread",
]


def start_ios_charge_api_server(
    handler: Callable[..., Any],
    *,
    host: str = "0.0.0.0",
    port: int = 8088,
    api_key: str = "",
    data_dir: str = "data/charge_api",
    loop=None,
    timeout: float = 15.0,
    settings: Settings = None,
    **kwargs,
):
    cfg = settings or Settings(
        host=kwargs.get("host", host),
        port=int(kwargs.get("port", port)),
        domain=str(kwargs.get("domain", "") or ""),
        https=bool(kwargs.get("https", False)),
        base_path=str(kwargs.get("base_path", "") or ""),
        allowed_hosts=list(kwargs.get("allowed_hosts") or []),
        trust_proxy=bool(kwargs.get("trust_proxy", False)),
        api_key=api_key,
        data_dir=data_dir,
        rate_limit=int(kwargs.get("rate_limit", 40)),
        rate_window=int(kwargs.get("rate_window", 60)),
        auth_fail_limit=int(kwargs.get("auth_fail_limit", 8)),
        auth_fail_window=int(kwargs.get("auth_fail_window", 300)),
        auth_ban_seconds=int(kwargs.get("auth_ban_seconds", 600)),
        max_body_bytes=int(kwargs.get("max_body_bytes", 50000)),
        handler_timeout=float(kwargs.get("handler_timeout", timeout)),
        request_timeout=float(kwargs.get("request_timeout", 15)),
        request_queue=int(kwargs.get("request_queue", 64)),
    )
    if settings is None:
        cfg.host = host
        cfg.port = port
        cfg.api_key = api_key
        cfg.data_dir = data_dir

    handler_cls = build_charge_api_handler(
        handler,
        api_key=cfg.api_key,
        data_dir=cfg.data_dir,
        loop=loop,
        timeout=cfg.handler_timeout,
        settings=cfg,
    )
    server = ChargeHTTPServer((cfg.host, cfg.port), handler_cls, queue_size=cfg.request_queue)
    print(f"[ios-deposit] 수신 중  {cfg.public_url}  POST /charge")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[ios-deposit] 종료")
        server.server_close()


def run_ios_deposit_api_server(bot_or_handler, process_charge_message_content=None, **kwargs):
    if process_charge_message_content is not None:
        bot = bot_or_handler
        handler = process_charge_message_content
        loop = resolve_loop(bot=bot)
        port = kwargs.pop("port", 88)
        return start_ios_charge_api_server(handler, port=port, loop=loop, **kwargs)
    if callable(bot_or_handler) and process_charge_message_content is None:
        return start_ios_charge_api_server(bot_or_handler, **kwargs)
    raise TypeError("run_ios_deposit_api_server(bot, handler) 또는 run_ios_deposit_api_server(handler)")


def start_ios_charge_api_server_thread(
    handler: Callable[..., Any],
    *,
    host: str = "0.0.0.0",
    port: int = 8088,
    api_key: str = "",
    data_dir: str = "data/charge_api",
    loop=None,
    timeout: float = 15.0,
    daemon: bool = True,
    settings: Settings = None,
    **kwargs,
) -> threading.Thread:
    thread = threading.Thread(
        target=start_ios_charge_api_server,
        kwargs={
            "handler": handler,
            "host": host,
            "port": port,
            "api_key": api_key,
            "data_dir": data_dir,
            "loop": loop,
            "timeout": timeout,
            "settings": settings,
            **kwargs,
        },
        daemon=daemon,
    )
    thread.start()
    return thread


def attach(handler: Callable[..., Any], **kwargs) -> threading.Thread:
    return start_ios_charge_api_server_thread(handler, **kwargs)


def attach_bot(bot, process_charge_message_content, **kwargs) -> threading.Thread:
    thread = threading.Thread(
        target=run_ios_deposit_api_server,
        args=(bot, process_charge_message_content),
        kwargs=kwargs,
        daemon=True,
    )
    thread.start()
    return thread
