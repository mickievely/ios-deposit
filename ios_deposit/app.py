import threading
from http.server import HTTPServer
from typing import Any, Callable

from ios_deposit.config.settings import Settings
from ios_deposit.handler import resolve_loop
from ios_deposit.router.http import build_charge_api_handler


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
        timeout=timeout,
        settings=cfg,
    )
    server = HTTPServer((cfg.host, cfg.port), handler_cls)
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
