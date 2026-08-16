import hmac

MIN_KEY_LEN = 16


def keys_match(provided: str, expected: str) -> bool:
    if not expected:
        return False
    got = provided or ""
    if len(got) != len(expected):
        hmac.compare_digest(expected, expected)
        return False
    return hmac.compare_digest(got, expected)


def header_authorized(headers, api_key: str) -> bool:
    return keys_match(headers.get("X-API-Key", ""), api_key)


def key_is_usable(api_key: str) -> bool:
    return bool(api_key) and len(api_key) >= MIN_KEY_LEN
