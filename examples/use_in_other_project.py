"""다른 프로젝트에서 ios-deposit 붙이는 예시.

그 프로젝트 폴더에서:
  pip install ios-deposit

이 폴더 코드 고치면서 같이 쓸 때:
  pip install -e 경로/ios-deposit
"""

from ios_deposit.app import attach, attach_bot, parse_deposit_message


def on_charge(message: str):
    parsed = parse_deposit_message(message)
    if not parsed:
        return False, None, "no match"
    print(parsed["amount"], parsed["depositor"])
    return True, None, f"{parsed['amount']:,}원"


def start_in_my_bot(bot, process_charge_message_content):
    bot._charge_api_loop = bot.loop
    attach_bot(bot, process_charge_message_content, api_key="충전전용키")


def start_with_my_handler(loop):
    attach(on_charge, port=8088, api_key="충전전용키", loop=loop)
