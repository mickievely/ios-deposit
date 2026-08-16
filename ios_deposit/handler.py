import asyncio
from typing import Any, Tuple, Union

ChargeResult = Union[Tuple[bool, Any, Any], dict, bool]


def normalize_handler_result(result: ChargeResult) -> Tuple[bool, Any, str]:
    if isinstance(result, dict):
        ok = bool(result.get("ok", result.get("matched", False)))
        uid = result.get("user_id", result.get("uid"))
        msg = str(result.get("message", result.get("detail", "") or ""))
        return ok, uid, msg
    if isinstance(result, bool):
        return result, None, ""
    if isinstance(result, tuple):
        if len(result) >= 3:
            return bool(result[0]), result[1], str(result[2] or "")
        if len(result) == 2:
            return bool(result[0]), result[1], ""
        if len(result) == 1:
            return bool(result[0]), None, ""
    return False, None, ""


def resolve_loop(loop=None, bot=None):
    if loop is not None:
        return loop
    if bot is not None:
        return getattr(bot, "_charge_api_loop", None) or getattr(bot, "loop", None)
    return None


def call_handler(handler, message: str, loop=None, timeout: float = 15.0) -> Tuple[bool, Any, str]:
    if asyncio.iscoroutinefunction(handler):
        event_loop = resolve_loop(loop=loop)
        if not event_loop:
            raise RuntimeError("async handler needs event loop")
        future = asyncio.run_coroutine_threadsafe(handler(message, None), event_loop)
        return normalize_handler_result(future.result(timeout=timeout))

    result = handler(message)
    if asyncio.iscoroutine(result):
        event_loop = resolve_loop(loop=loop)
        if not event_loop:
            raise RuntimeError("async handler needs event loop")
        future = asyncio.run_coroutine_threadsafe(result, event_loop)
        return normalize_handler_result(future.result(timeout=timeout))
    return normalize_handler_result(result)
