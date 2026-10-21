# bybit_api.py

import hmac
import hashlib
import json
import time
import requests
import pandas as pd

API_KEY = "lUMI4W5C40tmOFY0DS"
SECRET_KEY = "1bLR5sLZlAMZN968ISdr0fJWb0Smw4sMPzjU"
RECV_WINDOW = "5000"
BASE_URL = "https://api-demo.bybit.com"
#
# BASE_URL = "http://127.0.0.1:8000"
INTERVAL_MAP = {
    '1m': '1', '3m': '3', '5m': '5', '15m': '15', '30m': '30',
    '1h': '60', '2h': '120', '4h': '240', '1d': 'D',
}


class api_bybit:
    def __init__(self):
        self.api_key = API_KEY
        self.secret_key = SECRET_KEY
        self.recv_window = RECV_WINDOW
        self.base_url = BASE_URL

    def signed_headers(self, payload, timestamp=None):
        ts = timestamp or str(int(time.time() * 1000))
        param_str = ts + self.api_key + self.recv_window + payload
        sign = hmac.new(self.secret_key.encode(), param_str.encode(), hashlib.sha256).hexdigest()
        return {
            "X-BAPI-API-KEY": self.api_key,
            "X-BAPI-SIGN": sign,
            "X-BAPI-SIGN-TYPE": "2",
            "X-BAPI-TIMESTAMP": ts,
            "X-BAPI-RECV-WINDOW": self.recv_window,
            "Content-Type": "application/json",
        }

    def place_market_order(self, pair, side, quantity, reduce_only=True):
        """
        Маркет-ордер на Bybit V5.
        reduce_only=True — только закрывает позицию, не открывает новую.
        Возвращает orderId или None.
        """
        body = {
            "category": "linear",
            "symbol": pair,
            "side": side,  # "Buy" / "Sell"
            "orderType": "Market",
            "qty": str(quantity),
            "positionIdx": 0,  # One-Way Mode
            "reduceOnly": reduce_only,
        }
        payload = json.dumps(body)

        resp = requests.post(
            self.base_url + "/v5/order/create",
            headers=self.signed_headers(payload),
            data=payload,
            timeout=10,
        ).json()

        print(f"    Response: {resp}")
        if resp.get("retCode") == 0:
            return resp["result"]["orderId"]
        print(f"  ✗ Ошибка market: {resp}")
        return None

    def set_trigger_order(self, order):
        """
        Ставит триггер-ордер (Market) на Bybit V5.
        bot не используется — оставлен для совместимости сигнатуры.
        Возвращает orderId или None.
        """
        try:
            body = {
                "category": "linear",
                "symbol": order['symbol'],
                "side": order['side'],  # "Buy" / "Sell"
                "orderType": "Market",
                "qty": str(order['qty']),
                "triggerPrice": str(order['triggerPrice']),
                "triggerBy": "MarkPrice",
                "triggerDirection": order['triggerDirection'],
                "positionIdx": 0,  # One-Way Mode
                "timeInForce": "GTC",
            }
            payload = json.dumps(body)

            resp = requests.post(
                self.base_url + "/v5/order/create",
                headers=self.signed_headers(payload),
                data=payload,
                timeout=10,
            ).json()

            if resp.get("retCode") == 0:
                order_id = resp["result"]["orderId"]
                # print(f"  ✓ Триггер: {pair} \t{side} \t {quantity} @ {trigger_price:.6f}, ID={order_id}")
                print(f"  ✓ resp['result'] : {resp}")
                return order_id
            else:
                print(f"  ✗ Ошибка: {resp}")
                return None
        except Exception as e:
            print(f"  ✗ Ошибка: {e}")
            return None

    def cancel_order(self, order):
        """
        Отменяет ордер по orderId (Bybit V5).
        Возвращает resp (dict) или None при исключении.
        """
        print(f"Delete order with ID {order['order_id']}")
        body = {
            "category": "linear",
            "symbol": order['symbol'],
            "orderId": order['order_id'],
        }
        payload = json.dumps(body)
        try:
            return requests.post(
                self.base_url + "/v5/order/cancel",
                headers=self.signed_headers(payload),
                data=payload,
                timeout=10,
            ).json()
        except Exception as e:
            print(f"  ✗ Ошибка cancel_order: {e}")
            return None

    def cancel_all_orders(self, pair):
        """Отменяет все ордера по паре (Bybit V5)."""
        body = {"category": "linear", "symbol": pair}
        payload = json.dumps(body)
        return requests.post(
            self.base_url + "/v5/order/cancel-all",
            headers=self.signed_headers(payload),
            data=payload,
            timeout=10,
        ).json()

    def get_current_positions(self):
        """Получает открытые позиции с биржи (Bybit V5)"""
        positions = {}

        query = "category=linear&settleCoin=USDT"

        resp = requests.get(
            self.base_url + "/v5/position/list?" + query,
            headers=self.signed_headers(query),
            timeout=10,
        ).json()

        if resp.get("retCode") != 0:
            print(f"Ошибка позиций: {resp.get('retMsg')}")
            return {}

        for pos in resp["result"]["list"]:
            if float(pos["size"]) != 0:
                positions[pos["symbol"]] = {
                    "side": "LONG" if pos["side"] == "Buy" else "SHORT",
                    "entry_price": float(pos["avgPrice"]),
                    "positionAmt": float(pos["size"]),
                }

        return positions

    def fetch_klines(self, pair, interval, limit=128):
        """Загружает свечи с биржи"""
        # print(f"'interval' : {INTERVAL_MAP[interval]}, 'limit': {limit}")
        resp = requests.get(
            self.base_url + "/v5/market/kline",
            params={"category": "linear", "symbol": pair, "interval": INTERVAL_MAP[interval], "limit": limit},
            timeout=10,
        ).json()

        raw = resp["result"]["list"]  # [[start, open, high, low, close, volume, turnover], ...]
        df = pd.DataFrame(raw, columns=["time", "open", "high", "low", "close", "volume", "turnover"]).astype(float)

        if df['time'].iloc[0] > df['time'].iloc[-1]:
            #     # Обратный порядок — разворачиваем
            df = df.iloc[::-1].reset_index(drop=True)

        df["timestamp"] = pd.to_datetime(df["time"], unit="ms")

        return df


if __name__ == "__main__":
    api = api_bybit()
    # place_market_order(self, pair, side, quantity, reduce_only=True)
    print(api.place_market_order('1000PEPEUSDT', 'Buy', '100'))
