CHARGE_PATHS = {"/charge", "/api/charge/sms", "/api/ios/charge"}
HEALTH_PATH = "/health"


def normalize_path(raw_path: str) -> str:
    path = (raw_path or "/").split("?", 1)[0]
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    return path or "/"


def strip_base_path(path: str, base_path: str) -> str:
    if not base_path or base_path == "/":
        return path
    base = "/" + base_path.strip("/")
    if path == base:
        return "/"
    if path.startswith(base + "/"):
        stripped = path[len(base):]
        return stripped or "/"
    return path


def resolve_path(raw_path: str, base_path: str = "") -> str:
    return strip_base_path(normalize_path(raw_path), base_path)
