import requests



def get_server_time(base_url: str = "https://api-demo.bybit.com") -> dict:
    """
    Запрашивает время сервера Bybit.

    :param base_url: Базовый URL (демо: https://api-demo.bybit.com)
    :return: JSON-ответ с полями timeSecond и timeNano
    """
    response = requests.get(
        base_url + "/v5/market/time",
        timeout=10,
    )
    response.raise_for_status()
    return response.json()

def format_server_time(time_resp: dict) -> str:
    """Возвращает время сервера в читаемом виде (UTC)."""
    ms = int(time_resp["result"]["timeNano"]) // 1_000_000
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + " UTC"

if __name__ == "__main__":
    from datetime import datetime, timezone
    # ... твой код отмены ордеров ...

    print("\n--- Время сервера Bybit ---")
    time_resp = get_server_time(base_url ="http://127.0.0.1:8000")
    print("Сырой ответ:", time_resp)

    if time_resp.get("retCode") == 0:
        result = time_resp["result"]
        print(f"timeSecond: {result['timeSecond']}")
        print(f"timeNano:   {result['timeNano']}")

        readable = format_server_time(time_resp)
        print(f"Время сервера: {readable}")
    else:
        print(f"❌ Ошибка: {time_resp.get('retMsg')}")