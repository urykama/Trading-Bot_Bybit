import hmac
import hashlib
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


def get_positions(
    api_key: str,
    secret_key: str,
    settle_coin: str = "USDT",
    category: str = "linear",
    # base_url: str = "https://api-demo.bybit.com",
    base_url: str = "http://127.0.0.1:8000",
    recv_window: str = "5000",
) -> dict:
    """
    Запрашивает открытые позиции.

    :param api_key:      Публичный API-ключ
    :param secret_key:   Секретный API-ключ
    :param settle_coin:  Валюта расчёта (USDT / USDC). Возвращает только позиции с размером > 0
    :param category:     Тип продукта: linear / inverse / option
    :param base_url:     Базовый URL (демо: https://api-demo.bybit.com)
    :param recv_window:  Окно валидности запроса в мс (по умолчанию 5000)
    :return: JSON-ответ от Bybit в виде словаря
    """
    timestamp = str(int(time.time() * 1000))

    # Query-параметры для GET-запроса (не JSON!)
    # settleCoin обязателен, если не передан symbol [citation:1][citation:11]
    query = f"category={category}&settleCoin={settle_coin}"

    # Для GET-запросов подпись считается от query-строки
    signature = gen_signature(api_key, secret_key, recv_window, timestamp, query)

    headers = {
        "X-BAPI-API-KEY": api_key,
        "X-BAPI-SIGN": signature,
        "X-BAPI-SIGN-TYPE": "2",
        "X-BAPI-TIMESTAMP": timestamp,
        "X-BAPI-RECV-WINDOW": recv_window,
    }

    # GET-запрос: параметры идут в URL, а не в теле [citation:3]
    response = requests.get(
        base_url + "/v5/position/list?" + query,
        headers=headers,
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def print_positions(result: dict) -> None:
    """Печатает позиции в читаемом виде."""
    if result.get("retCode") != 0:
        print(f"❌ Ошибка: {result.get('retMsg')}")
        return

    positions = result.get("result", {}).get("list", [])

    # Фильтруем пустые позиции (size == "0")
    active = [p for p in positions if p.get("size") != "0"]

    if not active:
        print("Нет открытых позиций")
        return

    print(f"\n✅ Открытых позиций: {len(active)}")
    for p in active:
        print(
            f"   {p['symbol']:12} | "
            f"{p['side']:5} | "
            f"size={p['size']:10} | "
            f"avg={p['avgPrice']:10} | "
            f"liq={p.get('liqPrice', ''):10} | "
            f"pnl={p.get('unrealisedPnl', '')}"
        )


# ==========================================
# Тестовый запуск
# ==========================================
if __name__ == "__main__":
    API_KEY = "lUMI4W5C40tmOFY0DS"
    SECRET_KEY = "1bLR5sLZlAMZN968ISdr0fJWb0Smw4sMPzjU"   # <-- замени

    print("--- Открытые позиции (USDT) ---")
    result = get_positions(
        api_key=API_KEY,
        secret_key=SECRET_KEY,
        settle_coin="USDT",
        category="linear",
    )
    print("Сырой ответ:", result)
    print_positions(result)

'''
--- Открытые позиции (USDT) ---
Сырой ответ: {'retCode': 0, 'retMsg': 'OK', 'result': {'nextPageCursor': 'SOLUSDT%2C1791763200008%2C0', 'category': 'linear', 'list': [{'symbol': 'ETHUSDT', 'leverage': '25', 'breakEvenPrice': '2673.59250612', 'autoAddMargin': 0, 'avgPrice': '2674.16', 'liqPrice': '5192.65925314', 'riskLimitValue': '300000', 'takeProfit': '', 'positionValue': '77.082', 'isReduceOnly': False, 'positionIMByMp': '3.12916858', 'tpslMode': 'Full', 'riskId': 11, 'trailingStop': '0', 'liqPriceByMp': '', 'unrealisedPnl': '3.1428', 'markPrice': '2569.4', 'adlRankIndicator': 2, 'cumRealisedPnl': '-5.0268279', 'positionMM': '0.30025918', 'createdTime': '1790621732130', 'positionIdx': 0, 'openTime': 1790697607582, 'positionIM': '3.12916858', 'positionMMByMp': '0.30025918', 'seq': 140679292598637, 'updatedTime': '1791763200058', 'side': 'Sell', 'bustPrice': '', 'positionBalance': '0', 'leverageSysUpdatedTime': '', 'curRealisedPnl': '0.02708946', 'size': '0.03', 'positionStatus': 'Normal', 'mmrSysUpdatedTime': '', 'stopLoss': '', 'tradeMode': 0, 'sessionAvgPrice': ''}, {'symbol': 'BTCUSDT', 'leverage': '25', 'breakEvenPrice': '83678.52943118', 'autoAddMargin': 0, 'avgPrice': '83583.7', 'liqPrice': '5447.02240565', 'riskLimitValue': '300000', 'takeProfit': '', 'positionValue': '84.1448', 'isReduceOnly': False, 'positionIMByMp': '3.40992419', 'tpslMode': 'Full', 'riskId': 1, 'trailingStop': '0', 'liqPriceByMp': '', 'unrealisedPnl': '0.5611', 'markPrice': '84144.8', 'adlRankIndicator': 2, 'cumRealisedPnl': '-2.87708044', 'positionMM': '0.32181003', 'createdTime': '1790616265452', 'positionIdx': 0, 'openTime': 1791750617190, 'positionIM': '3.40992419', 'positionMMByMp': '0.32181003', 'seq': 140679292598611, 'updatedTime': '1791763200051', 'side': 'Buy', 'bustPrice': '', 'positionBalance': '0', 'leverageSysUpdatedTime': '', 'curRealisedPnl': '-0.04880624', 'size': '0.001', 'positionStatus': 'Normal', 'mmrSysUpdatedTime': '', 'stopLoss': '', 'tradeMode': 0, 'sessionAvgPrice': ''}, {'symbol': 'BNBUSDT', 'leverage': '25', 'breakEvenPrice': '752.49548363', 'autoAddMargin': 0, 'avgPrice': '753.4', 'liqPrice': '1360.49751995', 'riskLimitValue': '10000', 'takeProfit': '', 'positionValue': '98.1669', 'isReduceOnly': False, 'positionIMByMp': '3.98269882', 'tpslMode': 'Full', 'riskId': 251, 'trailingStop': '0', 'liqPriceByMp': '', 'unrealisedPnl': '-0.2249', 'markPrice': '755.13', 'adlRankIndicator': 2, 'cumRealisedPnl': '-2.39597198', 'positionMM': '0.71374105', 'createdTime': '1790621733309', 'positionIdx': 0, 'openTime': 1790697614414, 'positionIM': '3.98269882', 'positionMMByMp': '0.71374105', 'seq': 140679292598581, 'updatedTime': '1791763200019', 'side': 'Sell', 'bustPrice': '', 'positionBalance': '0', 'leverageSysUpdatedTime': '', 'curRealisedPnl': '-0.0637837', 'size': '0.13', 'positionStatus': 'Normal', 'mmrSysUpdatedTime': '', 'stopLoss': '', 'tradeMode': 0, 'sessionAvgPrice': ''}, {'symbol': 'XRPUSDT', 'leverage': '25', 'breakEvenPrice': '1.48516881', 'autoAddMargin': 0, 'avgPrice': '1.4852', 'liqPrice': '2.51910586', 'riskLimitValue': '50000', 'takeProfit': '', 'positionValue': '100.66256', 'isReduceOnly': False, 'positionIMByMp': '4.08698924', 'tpslMode': 'Full', 'riskId': 41, 'trailingStop': '0', 'liqPriceByMp': '', 'unrealisedPnl': '5.08368', 'markPrice': '1.4138', 'adlRankIndicator': 2, 'cumRealisedPnl': '-8.70901059', 'positionMM': '0.56379964', 'createdTime': '1790621732542', 'positionIdx': 0, 'openTime': 1790701213500, 'positionIM': '4.08698924', 'positionMMByMp': '0.56379964', 'seq': 140679292598571, 'updatedTime': '1791763200018', 'side': 'Sell', 'bustPrice': '', 'positionBalance': '0', 'leverageSysUpdatedTime': '', 'curRealisedPnl': '0.05593867', 'size': '71.2', 'positionStatus': 'Normal', 'mmrSysUpdatedTime': '', 'stopLoss': '', 'tradeMode': 0, 'sessionAvgPrice': ''}, {'symbol': 'SOLUSDT', 'leverage': '25', 'breakEvenPrice': '118.15830476', 'autoAddMargin': 0, 'avgPrice': '118.27', 'liqPrice': '210.97122199', 'riskLimitValue': '50000', 'takeProfit': '', 'positionValue': '90.0792', 'isReduceOnly': False, 'positionIMByMp': '3.65728835', 'tpslMode': 'Full', 'riskId': 281, 'trailingStop': '0', 'liqPriceByMp': '', 'unrealisedPnl': '4.5368', 'markPrice': '112.599', 'adlRankIndicator': 2, 'cumRealisedPnl': '-1.89665873', 'positionMM': '0.50451635', 'createdTime': '1790621732927', 'positionIdx': 0, 'openTime': 1790697611915, 'positionIM': '3.65728835', 'positionMMByMp': '0.50451635', 'seq': 140679292598565, 'updatedTime': '1791763200008', 'side': 'Sell', 'bustPrice': '', 'positionBalance': '0', 'leverageSysUpdatedTime': '', 'curRealisedPnl': '-0.03736653', 'size': '0.8', 'positionStatus': 'Normal', 'mmrSysUpdatedTime': '', 'stopLoss': '', 'tradeMode': 0, 'sessionAvgPrice': ''}]}, 'retExtInfo': {}, 'time': 1791788140844}

✅ Открытых позиций: 5
   ETHUSDT      | Sell  | size=0.03       | avg=2674.16    | liq=5192.65925314 | pnl=3.1428
   BTCUSDT      | Buy   | size=0.001      | avg=83583.7    | liq=5447.02240565 | pnl=0.5611
   BNBUSDT      | Sell  | size=0.13       | avg=753.4      | liq=1360.49751995 | pnl=-0.2249
   XRPUSDT      | Sell  | size=71.2       | avg=1.4852     | liq=2.51910586 | pnl=5.08368
   SOLUSDT      | Sell  | size=0.8        | avg=118.27     | liq=210.97122199 | pnl=4.5368

'''