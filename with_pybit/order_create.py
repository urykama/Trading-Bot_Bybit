import logging
import http.client as http_client
from pybit.unified_trading import HTTP

# ==========================================
# 1. НАСТРОЙКА ЛОГИРОВАНИЯ (ЧТОБЫ ВИДЕТЬ ЗАПРОС)
# ==========================================
# Включаем отладочный вывод для http.client.
# Это заставит Python печатать сырые данные, отправляемые по сети [citation:1][citation:4][citation:5].
http_client.HTTPConnection.debuglevel = 1

# Инициализируем логирование. Без этого вывод не появится [citation:5][citation:8].
logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)

# Включаем отладку для библиотеки urllib3, которая используется внутри requests (и, следовательно, pybit).
# Она покажет заголовки и тело запроса [citation:4][citation:10][citation:15].
requests_log = logging.getLogger("urllib3")
requests_log.setLevel(logging.DEBUG)
requests_log.propagate = True

# ==========================================
# 2. СОЗДАНИЕ СЕССИИ ДЛЯ ДЕМО-СЧЕТА
# ==========================================
# ВАЖНО: Используем demo=True и СВОИ демо-ключи.
# Это автоматически направит запросы на api-demo.bybit.com.
session = HTTP(
    demo=True,  # Флаг демо-режима
    api_key="lUMI4W5C40tmOFY0DS",  # <-- ЗАМЕНИТЕ
    api_secret="1bLR5sLZlAMZN968ISdr0fJWb0Smw4sMPzjU"  # <-- ЗАМЕНИТЕ
)

# ==========================================
# 3. ОТПРАВКА ТРИГГЕРНОГО (УСЛОВНОГО) ОРДЕРА
# ==========================================
try:
    print("\n--- ОТПРАВКА ЗАПРОСА ---\n")
    response = session.place_order(
        category="linear",  # Категория: линейные (USDT) фьючерсы
        symbol="BTCUSDT",  # Торговая пара
        side="Buy",  # Сторона: Buy (лонг) или Sell (шорт)
        orderType="Market",  # Тип ордера, который сработает ПОСЛЕ триггера
        qty="0.001",  # Количество
        triggerPrice="85000",  # ЦЕНА ТРИГГЕРА: когда цена дойдёт сюда, ордер активируется
        triggerBy="LastPrice",  # По какой цене проверять триггер: LastPrice, IndexPrice, MarkPrice

        triggerDirection=1,      # ключевое: срабатывание при росте цены
        # reduceOnly=True,  # Только уменьшать позицию (для стопа это логично)
        timeInForce="GTC"  # Время жизни ордера после срабатывания: Good Till Cancel
    )

    print("\n--- ОТВЕТ СЕРВЕРА ---\n")
    print(response)

    if response.get("retCode") == 0:
        print(f"\n✅ Ордер успешно создан. OrderID: {response['result']['orderId']}")
    else:
        print(f"\n❌ Ошибка: {response.get('retMsg')}")

except Exception as e:
    print(f"\n❌ Ошибка соединения: {e}")

'''
--- ОТПРАВКА ЗАПРОСА ---

DEBUG:pybit._http_manager:Initializing HTTP session.
DEBUG:urllib3.connectionpool:Starting new HTTPS connection (1): api-demo.bybit.com:443

send: 
b'POST 
/v5/order/create HTTP/1.1\r\n
Host: api-demo.bybit.com\r\n
User-Agent: python-requests/2.34.2\r\n
Accept-Encoding: gzip, deflate, zstd\r\n
Accept: application/json\r\n
Connection: keep-alive\r\n
Content-Type: application/json\r\n
X-BAPI-API-KEY: lUMI4W5C40tmOFY0DS\r\n
X-BAPI-SIGN: 68fc52252089f3ced99a1dc8b36b31bed76407d449892d3aecbb7162e7504165\r\n
X-BAPI-SIGN-TYPE: 2\r\n
X-BAPI-TIMESTAMP: 1791744776100\r\n
X-BAPI-RECV-WINDOW: 5000\r\n
Content-Length: 213\r\n\r\n'

send: b'{
"category": "linear", 
"symbol": "BTCUSDT", 
"side": "Buy", 
"orderType": "Market", 
"qty": "0.001", 
"triggerPrice": "85000", 
"triggerBy": "LastPrice", 
"triggerDirection": 1, 
"reduceOnly": true, 
"timeInForce": "GTC"
}'
DEBUG:urllib3.connectionpool:https://api-demo.bybit.com:443 "POST /v5/order/create HTTP/1.1" 200 141

reply: 'HTTP/1.1 200 OK\r\n'
header: Content-Type: application/json; charset=utf-8
header: Content-Length: 141
header: Connection: keep-alive
header: Date: Sun, 11 Oct 2026 18:52:56 GMT
header: x-cld-src: Loc-A
header: X-Bapi-Limit: 10
header: X-Bapi-Limit-Status: 9
header: X-Bapi-Limit-Reset-Timestamp: 1791744776747
header: Ret_code: 0
header: Traceid: 27980fe6c889f30452d5b321169e28b5
header: Timenow: 1791744776748
header: Server: Openresty
header: X-Cache: Miss from cloudfront
header: Via: 1.1 4737976a27f5e96a307bca1f8a140466.cloudfront.net (CloudFront)
header: X-Amz-Cf-Pop: HEL51-P2
header: X-Amz-Cf-Id: EXh8X5xdhb7uBjD32C3nYwbK4lt5No0J5RV814bT_Lyio587F-_-7A==

--- ОТВЕТ СЕРВЕРА ---

{'retCode': 0, 'retMsg': 'OK', 'result': {'orderId': '8ffe77d3-4e8d-4c5a-a22b-9ed40050ac32', 'orderLinkId': ''}, 'retExtInfo': {}, 'time': 1791744776748}

✅ Ордер успешно создан. OrderID: 8ffe77d3-4e8d-4c5a-a22b-9ed40050ac32

'''