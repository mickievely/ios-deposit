<p align="center">
  <img src="https://img.shields.io/badge/ios--deposit-입금%20수신%20서버-111111?style=for-the-badge" alt="ios-deposit" />
</p>

<p align="center">
  아이폰 카카오뱅크 입금 알림을 받아서<br/>
  디스코드 자판기, 웹 자판기, 쇼핑몰, 자동화 서버로 넘깁니다.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9+-3776AB?logo=python&logoColor=white" alt="Python 3.9+" />
  <img src="https://img.shields.io/pypi/v/ios-deposit?label=pip&color=3775A9" alt="pip" />
  <img src="https://img.shields.io/badge/카카오뱅크-3333%20%2F%207777-FFCD00?logo=kakaotalk&logoColor=000" alt="KakaoBank" />
</p>

> [!IMPORTANT]
> 카카오뱅크 **3333**, **7777** 계좌만 됩니다. 다른 은행은 안 됩니다.

```
아이폰 단축어  →  ios-deposit  →  봇 / 웹자판기 / 쇼핑몰
```

---

## 설치하고 켜기

```bash
pip install ios-deposit
ios-deposit
```

처음 켜면 그 폴더에 `config.json` 이 생깁니다.

깃허브에서 받은 폴더로 켤 때는 `python app.py` 해도 됩니다.

---

## 키 넣기

키 없으면 서버가 안 켜집니다. 16자 이상 랜덤으로 만들어서 `config.json` 에 넣으세요.
봇 토큰이랑 같은 거 쓰지 마세요. 키는 헤더로만 보냅니다.

```json
{
  "api_key": "여기-충전전용-키"
}
```

아이폰 단축어 헤더에도 **똑같은 값**을 넣습니다.

```
X-API-Key: 여기-충전전용-키
```

---

## 아이폰에서 보내기

이 프로그램은 `8088` 포트에서 기다립니다.

아이피로 쓸 때

```
POST http://서버아이피:8088/charge
```

도메인이 있으면 `config.json` 에만 적으면 됩니다.

```json
{
  "domain": "https://pay.example.com"
}
```

단축어 주소는 `https://pay.example.com/charge` 입니다.

보낼 내용

```json
{
  "message": "[카카오뱅크]\n입금 10,000원\n홍길동\n잔액 123,456원"
}
```

헤더

```
Content-Type: application/json
X-API-Key: 여기-충전전용-키
```

브라우저에서 `http://서버아이피:8088/health` 가 열리면 서버는 켜진 겁니다.
집에서 쓸 때는 공유기에서 `8088` 포트를 열어주세요.

도메인을 쓰려면 도메인을 서버 아이피로 연결하고, Cloudflare/nginx에서 `80` `443` 을 `127.0.0.1:8088` 로 넘기면 됩니다.

---

## 잘 됐는지

성공

```json
{"ok": true, "parsed": {"amount": 10000, "depositor": "홍길동"}}
```

지원 안 하는 계좌

```json
{"ok": false, "error": "카카오뱅크 3333 / 7777 계좌만 지원합니다"}
```

같은 문자가 또 오면

```json
{"ok": false, "duplicate": true}
```

---

## 웹 자판기 / 쇼핑몰 / 다른 서버로 넘기기

받을 쪽 주소만 `config.json` 에 넣으면 됩니다. PHP든 Node든 파이썬이든, POST 받을 수 있으면 됩니다.

```json
{
  "webhook_url": "https://내사이트.com/api/charge/sms"
}
```

입금이 오면 그 주소로 이게 갑니다.

```json
{
  "message": "원본 문자 전체",
  "parsed": {"amount": 10000, "depositor": "홍길동"},
  "received_at": "2026-06-08T12:34:56"
}
```

받는 쪽에서 `{"ok": true}` 를 주면 됩니다.

로컬 테스트

```bash
python examples/web_receiver.py
```

그때 `webhook_url` 은 `http://127.0.0.1:5000/api/charge/sms` 로 두면 됩니다.

---

## 다른 파이썬 프로젝트에 붙이기

```bash
pip install ios-deposit
```

이 폴더 코드를 고치면서 같이 쓸 때는

```bash
pip install -e ../ios-deposit
```

디스코드 자판기 봇

```python
from ios_deposit import attach_bot

bot._charge_api_loop = bot.loop
attach_bot(bot, process_charge_message_content, api_key="충전전용키")
```

직접 처리

```python
from ios_deposit import attach, parse_deposit_message

def on_charge(message: str):
    parsed = parse_deposit_message(message)
    if not parsed:
        return False, None, "no match"
    return True, None, f"{parsed['amount']:,}원"

attach(on_charge, port=8088, api_key="충전전용키", loop=bot.loop)
```

---

## 설정

`config.json` 에서 자주 만지는 것만 보면 됩니다.

| 이름 | 뭐 하는 거 |
|---|---|
| `api_key` | 충전 전용 키. 단축어랑 같아야 함 |
| `domain` | 도메인. 예: `https://pay.example.com` |
| `webhook_url` | 웹자판기/쇼핑몰로 넘길 주소 |
| `port` | 기본 `8088` |

키 넣은 `config.json` 은 깃에 올리지 마세요.
