import hashlib
import hmac
import json
import time
import requests

# ==========================================
# 1. НАСТРОЙКИ
# ==========================================
API_KEY = "lUMI4W5C40tmOFY0DS"      # <-- твой демо-ключ
SECRET_KEY = "1bLR5sLZlAMZN968ISdr0fJWb0Smw4sMPzjU"     # <-- твой демо-секрет
# BASE_URL = "https://api-demo.bybit.com"
BASE_URL = "http://127.0.0.1:8000"
ENDPOINT = "/v5/order/create"
RECV_WINDOW = "5000"

# ==========================================
# 2. ГЕНЕРАЦИЯ ПОДПИСИ (то, что делал pybit)
# ==========================================
def gen_signature(timestamp, payload):
    """
    Формула Bybit: HMAC_SHA256(secret, timestamp + api_key + recv_window + body)
    """
    param_str = str(timestamp) + API_KEY + RECV_WINDOW + payload
    signature = hmac.new(
        SECRET_KEY.encode("utf-8"),
        param_str.encode("utf-8"),
        hashlib.sha256
    )
    return signature.hexdigest()

# ==========================================
# 3. ФОРМИРОВАНИЕ ЗАПРОСА
# ==========================================
# Timestamp в миллисекундах
timestamp = str(int(time.time() * 1000))

# Тело запроса — точно такой же JSON, как отправлял pybit
payload_dict = {
    "category": "linear",
    "symbol": "BTCUSDT",
    # "symbol": "ETHUSDT",
    "side": "Sell",  # "Buy"
    "orderType": "Market",
    "qty": "0.01",
    "triggerPrice": "113750",
    "triggerBy": "LastPrice",
    "triggerDirection": 2,
    "timeInForce": "GTC"
}

# JSON-строка (именно её подписываем)
payload = json.dumps(payload_dict)

# Подпись
signature = gen_signature(timestamp, payload)

# Заголовки — вручную, как в логе
headers = {
    "X-BAPI-API-KEY": API_KEY,
    "X-BAPI-SIGN": signature,
    "X-BAPI-SIGN-TYPE": "2",
    "X-BAPI-TIMESTAMP": timestamp,
    "X-BAPI-RECV-WINDOW": RECV_WINDOW,
    "Content-Type": "application/json",
}

# ==========================================
# 4. ОТПРАВКА
# ==========================================
print("--- ОТПРАВКА ЗАПРОСА ---")
response = requests.post(
    BASE_URL + ENDPOINT,
    headers=headers,
    data=payload
)

print(f"Статус: {response.status_code}")
print(f"Ответ: {response.text}")

# ==========================================
# 5. РАЗБОР ОТВЕТА
# ==========================================
result = response.json()

if result.get("retCode") == 0:
    print(f"\n✅ Ордер создан. OrderID: {result['result']['orderId']}")
else:
    print(f"\n❌ Ошибка: {result.get('retMsg')}")