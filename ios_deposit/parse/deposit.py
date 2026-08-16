import re
from typing import Optional

UNSUPPORTED_ACCOUNT = "카카오뱅크 3333 / 7777 계좌만 지원합니다"


def is_supported_kakao_account(text: str) -> bool:
    return "카카오뱅크" in (text or "").replace(" ", "")


def parse_deposit_message(content: str) -> Optional[dict]:
    text = (content or "").strip()
    if not text:
        return None
    if not is_supported_kakao_account(text):
        return None

    amt_match = re.search(r"입금\s*([\d,]+)원", text)
    if not amt_match:
        return None
    amount = int(amt_match.group(1).replace(",", ""))

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    depositor = None

    def valid_name(line: str) -> bool:
        if not re.search(r"[가-힣]", line):
            return False
        if "(" in line or ")" in line or "*" in line or re.search(r"\d", line):
            return False
        if "원" in line or "잔액" in line or line.startswith("["):
            return False
        normalized = re.sub(r"[^가-힣]", "", line)
        return 2 <= len(normalized) <= 4

    for i, ln in enumerate(lines):
        if "입금" in ln and i + 1 < len(lines) and valid_name(lines[i + 1]):
            depositor = lines[i + 1]
            break

    if depositor is None:
        for i, ln in enumerate(lines):
            if ln.startswith("잔액") and i > 0 and valid_name(lines[i - 1]):
                depositor = lines[i - 1]
                break

    if depositor is None:
        for ln in reversed(lines):
            if valid_name(ln):
                depositor = ln
                break

    if depositor is None:
        inline = re.search(r"입금\s*[\d,]+원\s+([가-힣]{2,4})\s+잔액", text)
        if inline:
            depositor = inline.group(1).strip()

    if not depositor:
        return None
    return {"amount": amount, "depositor": depositor.strip()}
