import hmac
import hashlib
import json
import time
import requests


def gen_signature(api_key: str, secret_key: str, recv_window: str,
                  timestamp: str, payload: str) -> str:
    """
    Генерирует HMAC-SHA256 подпись для Bybit V5.
    Формула: HMAC_SHA256(secret, timestamp + api_key + recv_window + payload)
    """
    param_str = timestamp + api_key + recv_window + payload
    return hmac.new(
        secret_key.encode("utf-8"),
        param_str.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


def cancel_all_orders(
    api_key: str,
    secret_key: str,
    symbol: str,
    category: str = "linear",
    # base_url: str = "https://api-demo.bybit.com",
    base_url: str = "http://127.0.0.1:8000",
    recv_window: str = "5000",
    order_filter: str | None = None,
) -> dict:
    """
    Отменяет все ордера по указанной торговой паре.

    :param api_key:      Публичный API-ключ
    :param secret_key:   Секретный API-ключ
    :param symbol:       Торговая пара, например "BTCUSDT"
    :param category:     Тип продукта: linear / inverse / spot / option
    :param base_url:     Базовый URL (демо: https://api-demo.bybit.com)
    :param recv_window:  Окно валидности запроса в мс (по умолчанию 5000)
    :param order_filter: Необязательно: Order / StopOrder / tpslOrder / OcoOrder
                         Если не указан — отменяются ВСЕ типы ордеров
    :return: JSON-ответ от Bybit в виде словаря
    """
    # Текущее время в миллисекундах (UTC)
    timestamp = str(int(time.time() * 1000))

    # Тело запроса
    payload_dict: dict = {
        "category": category,
        "symbol": symbol,
    }
    if order_filter:
        payload_dict["orderFilter"] = order_filter

    # JSON-строка — именно её подписываем
    payload = json.dumps(payload_dict)

    # Подпись
    signature = gen_signature(api_key, secret_key, recv_window, timestamp, payload)

    # Заголовки
    headers = {
        "X-BAPI-API-KEY": api_key,
        "X-BAPI-SIGN": signature,
        "X-BAPI-SIGN-TYPE": "2",
        "X-BAPI-TIMESTAMP": timestamp,
        "X-BAPI-RECV-WINDOW": recv_window,
        "Content-Type": "application/json",
    }

    # Отправка запроса
    response = requests.post(
        base_url + "/v5/order/cancel-all",
        headers=headers,
        data=payload,
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def print_cancel_result(result: dict) -> None:
    """Печатает результат отмены в читаемом виде."""
    if result.get("retCode") == 0:
        order_list = result.get("result", {}).get("list", [])
        if order_list:
            print(f"\n✅ Успешно отменено ордеров: {len(order_list)}")
            for o in order_list:
                print(f"   - {o.get('orderId')} (success={o.get('success')})")
        else:
            print("\n✅ Запрос принят (по данной паре нет активных ордеров)")
    else:
        print(f"\n❌ Ошибка отмены: {result.get('retMsg')}")


# ==========================================
# Тестовый запуск
# ==========================================
if __name__ == "__main__":
    API_KEY = "lUMI4W5C40tmOFY0DS"
    SECRET_KEY = "1bLR5sLZlAMZN968ISdr0fJWb0Smw4sMPzjU"   # <-- замени на свой demo secret
    SYMBOL = "BTCUSDT"

    print(f"--- Отмена всех ордеров по {SYMBOL} ---")
    result = cancel_all_orders(
        api_key=API_KEY,
        secret_key=SECRET_KEY,
        symbol=SYMBOL,
        category="linear",
    )
    print("Сырой ответ:", result)
    print_cancel_result(result)