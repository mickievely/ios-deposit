import json
import os
import shutil
import sys

from ios_deposit.auth.api_key import MIN_KEY_LEN, key_is_usable
from ios_deposit.config.settings import Settings
from ios_deposit.parse.deposit import parse_deposit_message
from ios_deposit.webhook.client import create_webhook_handler
from ios_deposit.app import start_ios_charge_api_server


def _fix_stdio():
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def packaged_example() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.example.json")


def ensure_config(base_dir: str) -> str:
    config_path = os.path.join(base_dir, "config.json")
    if os.path.isfile(config_path):
        return config_path

    for example_path in (
        os.path.join(base_dir, "config.example.json"),
        packaged_example(),
    ):
        if os.path.isfile(example_path):
            shutil.copyfile(example_path, config_path)
            print("config.json 이 없어서 예제를 복사했습니다. 필요하면 값을 바꾼 뒤 다시 실행하세요.")
            return config_path

    print("config.json 이 없습니다.")
    sys.exit(1)


def build_handler(cfg: Settings):
    if cfg.webhook_url:
        return create_webhook_handler(
            cfg.webhook_url,
            api_key=cfg.webhook_api_key,
            timeout=cfg.webhook_timeout,
        )

    def log_only_handler(message: str):
        parsed = parse_deposit_message(message)
        if parsed:
            print(f"[ios-deposit] 파싱됨 — {parsed['amount']:,}원 / {parsed['depositor']}")
            return True, None, f"{parsed['amount']:,}원 {parsed['depositor']}"
        print("[ios-deposit] 파싱 실패 또는 매칭 없음")
        return False, None, "no match"

    return log_only_handler


def main(base_dir: str = None):
    _fix_stdio()
    if base_dir is None:
        base_dir = os.getcwd()
    raw = load_config(ensure_config(base_dir))
    data_dir = os.path.join(base_dir, str(raw.get("data_dir", "data/charge_api")))
    cfg = Settings.from_dict(raw, data_dir=data_dir)

    print()
    print("  ios-deposit")
    print(f"  listen   http://{cfg.host}:{cfg.port}")
    print(f"  public   {cfg.public_url}")
    print(f"  charge   POST {cfg.charge_url}")
    print(f"  health   GET  {cfg.health_url}")
    if cfg.domain:
        print(f"  domain   {cfg.domain}  ({'https' if cfg.https else 'http'})")
    if not key_is_usable(cfg.api_key):
        print(f"  api_key  가 없거나 {MIN_KEY_LEN}자보다 짧습니다. config.json 에 충전 전용 키를 넣으세요.")
        sys.exit(1)
    print("  api_key  사용 중 (헤더 X-API-Key)")
    if cfg.webhook_url:
        print(f"  webhook  {cfg.webhook_url}")
    else:
        print("  webhook  없음 — 수신·저장만 함")
    print()

    start_ios_charge_api_server(build_handler(cfg), settings=cfg)
