# sar_bot_v2.py

import pandas as pd
import hmac
import hashlib
import json
import time
import requests
# from BingX_demo_250605 import BingX
from sar_strategy import (
    calculate_sar,
    find_intervals,
    get_reversal_info,
)



# ========== НАСТРОЙКИ ==========
BASE_USDT = 1000  # Базовый размер позиции в USDT
INTERVAL = '1h'  # Таймфрейм по умолчанию
INTERVALS_TO_SEC = {
    '1m': 60, '3m': 180, '5m': 300, '15m': 900, '30m': 1800,
    '1h': 3600, '2h': 7200, '4h': 14400, '1d': 86400,
}
INTERVAL_MAP = {
    '1m': '1', '3m': '3', '5m': '5', '15m': '15', '30m': '30',
    '1h': '60', '2h': '120', '4h': '240', '1d': 'D',
}

STEPS = {
    "1":     0,
    "0.1":   1,
    "0.01":  2,
    "0.001": 3,
    "0.0001": 4,
    "0.00001": 5,
    "0.000001": 6,
    "0.0000001": 7,
    "0.00000001": 8,
}

API_KEY = "lUMI4W5C40tmOFY0DS"
SECRET_KEY = "1bLR5sLZlAMZN968ISdr0fJWb0Smw4sMPzjU"        # <-- замени
RECV_WINDOW = "5000"
# BASE_URL = "https://api-demo.bybit.com"
BASE_URL = "http://127.0.0.1:8000"


def _signed_headers(payload: str) -> dict:
    """Формирует подписанные заголовки для Bybit V5."""
    ts = str(int(time.time() * 1000))
    param_str = ts + API_KEY + RECV_WINDOW + payload
    sign = hmac.new(
        SECRET_KEY.encode("utf-8"),
        param_str.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    return {
        "X-BAPI-API-KEY": API_KEY,
        "X-BAPI-SIGN": sign,
        "X-BAPI-SIGN-TYPE": "2",
        "X-BAPI-TIMESTAMP": ts,
        "X-BAPI-RECV-WINDOW": RECV_WINDOW,
        "Content-Type": "application/json",
    }

def signed_headers(api_key, secret_key, recv_window, payload, timestamp=None):
    ts = timestamp or str(int(time.time() * 1000))
    param_str = ts + api_key + recv_window + payload
    sign = hmac.new(secret_key.encode(), param_str.encode(), hashlib.sha256).hexdigest()
    return {
        "X-BAPI-API-KEY": api_key,
        "X-BAPI-SIGN": sign,
        "X-BAPI-SIGN-TYPE": "2",
        "X-BAPI-TIMESTAMP": ts,
        "X-BAPI-RECV-WINDOW": recv_window,
        "Content-Type": "application/json",
    }


def set_trigger_order(pair, side, trigger_price, quantity):
    """
    Ставит триггер-ордер (Market) на Bybit V5.
    bot не используется — оставлен для совместимости сигнатуры.
    Возвращает orderId или None.
    """
    try:
        body = {
            "category": "linear",
            "symbol": pair,
            "side": side,                        # "Buy" / "Sell"
            "orderType": "Market",
            "qty": str(quantity),
            "triggerPrice": str(trigger_price),
            "triggerBy": "MarkPrice",
            "triggerDirection": 1 if side == "Buy" else 2,
            "positionIdx": 0,                    # One-Way Mode
            "timeInForce": "GTC",
        }
        payload = json.dumps(body)

        resp = requests.post(
            BASE_URL + "/v5/order/create",
            headers=_signed_headers(payload),
            data=payload,
            timeout=10,
        ).json()

        if resp.get("retCode") == 0:
            order_id = resp["result"]["orderId"]
            print(f"  ✓ Триггер: {pair} \t{side} \t {quantity} @ {trigger_price:.6f}, ID={order_id}")
            return order_id
        else:
            print(f"  ✗ Ошибка: {resp}")
            return None
    except Exception as e:
        print(f"  ✗ Ошибка: {e}")
        return None

def cancel_all_orders(pair):
    """Отменяет все ордера по паре (Bybit V5)."""
    body = {"category": "linear", "symbol": pair}
    payload = json.dumps(body)
    return requests.post(
        BASE_URL + "/v5/order/cancel-all",
        headers=_signed_headers(payload),
        data=payload,
        timeout=10,
    ).json()

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
def get_current_positions():
    """Получает открытые позиции с биржи (Bybit V5)"""
    positions = {}

    # Query-строка — её подписываем
    query = "category=linear&settleCoin=USDT"

    resp = requests.get(
        BASE_URL + "/v5/position/list?" + query,
        headers=signed_headers(
            api_key=API_KEY,
            secret_key=SECRET_KEY,
            recv_window=RECV_WINDOW,
            payload=query,          # подпись от query-строки
        ),
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


def fetch_klines(pair, interval=INTERVAL, limit=128):
    """Загружает свечи с биржи"""
    # klines = bot.klines(symbol=pair, interval=interval, limit=limit)
    # # print(klines)
    # if 'data' not in klines:
    #     return None
    #
    # df = pd.DataFrame(klines['data']).astype(float)
    # df.sort_values('time', inplace=True)
    # df['timestamp'] = pd.to_datetime(df['time'] * 0.001 + 3600 * 5, unit='s')
    # print(df['timestamp'].iloc[-1])
    # df.rename(columns={'open': 'open', 'high': 'high', 'low': 'low', 'close': 'close'}, inplace=True)
    resp = requests.get(
        BASE_URL + "/v5/market/kline",
        params={"category": "linear", "symbol": pair, "interval": "60", "limit": limit},
        timeout=10,
    ).json()

    raw = resp["result"]["list"]  # [[start, open, high, low, close, volume, turnover], ...]
    df = pd.DataFrame(raw, columns=["time", "open", "high", "low", "close", "volume", "turnover"]).astype(float)
    df.sort_values("time", inplace=True)
    df["timestamp"] = pd.to_datetime(df["time"], unit="ms")

    return df


# ========== КЛАСС ТОРГОВОГО БОТА ДЛЯ ОДНОЙ ПАРЫ ==========
class SARTrader:
    def __init__(self, pair, position_side, entry_price, position_amt, filters, base_usdt=BASE_USDT):

        self.pair = pair
        self.base_usdt = base_usdt
        self.position = 1 if position_side == 'LONG' else -1
        self.entry_price = entry_price
        self.positionAmt = position_amt
        self.position_size = 1.0
        self.last_loss = False
        self.trigger_order_id = None
        self.trigger_price = 0
        self.current_interval_idx = -1
        self.last_trigger_price = 0
        self.pending_trigger = False
        self.entry_direction = None
        self.side = None
        self.filters = filters
        self.filters[self.pair]["qtyStep"]
        self.filters[self.pair]["minOrderQty"]

        print(f"  Трейдер создан для {pair}: позиция {self.position}, объём {self.positionAmt}")

    def get_base_quantity(self, price):
        """Возвращает базовое количество монет на self.base_usdt"""
        return self.base_usdt / price

    def sync_with_exchange(self, open_positions):
        """Синхронизирует состояние с биржей"""
        if self.pair in open_positions:
            pos = open_positions[self.pair]
            new_position = 1 if pos['side'] == 'LONG' else -1
            if new_position != self.position:
                print(f"  [{self.pair}] Позиция изменилась на бирже: {self.position} -> {new_position}")
                self.position = new_position
                self.entry_price = pos['entry_price']
                self.positionAmt = pos['positionAmt']
                # Сбрасываем триггер
                self.trigger_order_id = None
                self.trigger_price = 0
                self.last_trigger_price = 0
                self.pending_trigger = False
        else:
            if self.position != 0:
                print(f"  [{self.pair}] Позиция закрыта на бирже")
                self.position = 0
                self.trigger_order_id = None
                self.pending_trigger = False

    def get_best_trigger_price(self, new_price):
        """
        Выбирает лучшую цену триггера:
        - для LONG: минимальную (ниже — лучше вход)
        - для SHORT: максимальную (выше — лучше вход)
        """
        candidates = []
        if self.last_trigger_price > 0:
            candidates.append(self.last_trigger_price)
        if new_price > 0:
            candidates.append(new_price)
        if not candidates:
            return new_price

        if self.entry_direction == 'LONG':

            best = min(candidates)
            if best != self.last_trigger_price and self.last_trigger_price > 0:
                print(f"            [{self.pair}] Цена LONG улучшена: {self.last_trigger_price:.2f} -> {best:.2f}")

        else:  # SHORT

            best = max(candidates)
            if best != self.last_trigger_price and self.last_trigger_price > 0:
                print(f"            [{self.pair}] Цена SHORT улучшена: {self.last_trigger_price:.2f} -> {best:.2f}")

        return best

    def place_trigger(self, trigger_price, quantity):

        # Проверяем, нужен ли новый ордер
        if self.pending_trigger and self.trigger_price == trigger_price:
            print(f"  [{self.pair}] Триггер уже существует с ценой {trigger_price:.2f}, пропускаем")
            return False

        # Удаляем старые триггеры
        try:
            cancel_all_orders(self.pair)
            # print(f"  [{self.pair}] Удалены старые триггеры")
        except Exception as e:
            print(f"  [{self.pair}] Ошибка удаления: {e}")

        # Ставим новый
        order_id = set_trigger_order(self.pair, self.side, trigger_price, quantity)
        if order_id:
            self.trigger_order_id = order_id
            self.trigger_price = trigger_price
            self.last_trigger_price = trigger_price
            self.pending_trigger = True
            # print(f"  ✓ [{self.pair}] Триггер {self.entry_direction} {self.side} @ {trigger_price:.2f}, кол-во: {quantity:.4f}")
            return True
        return False

    def process(self, df, open_positions):
        """Основная логика обработки пары"""
        # 1. Синхронизация с биржей
        self.sync_with_exchange(open_positions)

        # Определяем направление разворота
        if self.position == 1:  # LONG -> разворот в SHORT
            self.entry_direction = 'SHORT'
            self.side = 'Sell'
        elif self.position == -1:  # SHORT -> разворот в LONG
            self.entry_direction = 'LONG'
            self.side = 'Buy'
        else:  # Если позиции нет — удаляем трейдера
            print(f"  [{self.pair}] Позиция закрыта, трейдер будет удалён")
            return False

        # 2. Расчёт SAR
        df = calculate_sar(df)
        df = df.dropna(subset=['sar_signed'])
        if len(df) < 2:
            return True

        # 3. Интервалы и сигналы
        intervals = find_intervals(df)
        reversals = get_reversal_info(intervals)
        if not reversals:
            return True

        current_price = df['close'].iloc[-1]
        curr_idx = len(intervals) - 1

        # 4. Ищем актуальный разворотный сигнал (противоположный текущей позиции)
        active_rev = None
        for rev in reversed(reversals):
            if (self.position == 1 and rev['direction'] == 'SHORT') or \
                    (self.position == -1 and rev['direction'] == 'LONG'):
                active_rev = rev
                break

        if active_rev is None:
            return True

        # 5. Получаем новую цену триггера из сигнала
        new_trigger_price = active_rev['price']

        # 6. Выбираем лучшую цену (сравниваем с текущей, если триггер уже стоит)
        best_price = self.get_best_trigger_price(new_trigger_price)

        # 7. Проверяем, нужно ли обновлять триггер
        need_update = False
        if not self.pending_trigger:
            # Триггера нет — нужно поставить
            need_update = True
        elif self.trigger_price != best_price:
            # Цена изменилась — нужно обновить
            need_update = True
            # print(f"                [{self.pair}] Цена триггера изменилась: {self.trigger_price:.2f} -> {best_price:.2f}")

        # 8. Если нужно обновить — ставим новый триггер
        if need_update:
            # quantity = abs(self.positionAmt) + self.get_base_quantity(current_price) * self.position_size
            quantity = abs(self.positionAmt) + self.get_base_quantity(df['sar'].iloc[-1]) * self.position_size
            # quantity = 0.008
            print(quantity, "\t\t", self.get_base_quantity(current_price), "\t\t", abs(self.positionAmt))
            # Округление qty до qtyStep и проверка minOrderQty
            step = self.filters[self.pair]["qtyStep"]
            min_qty = self.filters[self.pair]["minOrderQty"]
            quantity = max((quantity // step) * step, min_qty)
            n = STEPS[str(step)]
            quantity = f"{quantity:.{n}f}"
            self.place_trigger(best_price, quantity)
            self.current_interval_idx = curr_idx
        else:
            # Триггер уже существует с оптимальной ценой — ничего не делаем
            if self.pending_trigger:
                pass  # можно добавить отладочный вывод при необходимости

        return True

# ========== ОСНОВНОЙ ЦИКЛ ==========
def run(traders, filters):
    """Основной цикл"""
    open_positions = get_current_positions()

    # Обновляем существующих трейдеров и удаляем тех, у кого нет позиции
    pairs_to_remove = []
    for pair, trader in traders.items():
        if pair not in open_positions:
            print(f"  Позиция {pair} закрыта, удаляем трейдера")
            pairs_to_remove.append(pair)

    for pair in pairs_to_remove:
        del traders[pair]

    # Создаём новых трейдеров для новых позиций
    # Здесь передать при создании экземпляров класса
    for pair, pos_data in open_positions.items():
        if pair not in traders:
            traders[pair] = SARTrader(
                pair,
                pos_data['side'],
                pos_data['entry_price'],
                pos_data['positionAmt'],
                filters,                    # <-- 5-й аргумент
                BASE_USDT
            )

    # Обрабатываем каждого трейдера
    for pair, trader in list(traders.items()):
        try:
            df = fetch_klines( pair)
            if df is None:
                continue
            should_keep = trader.process(df, open_positions)
            if not should_keep:
                del traders[pair]
        except Exception as e:
            print(f"  Ошибка {pair}: {e}")


def timer():
    """Таймер"""
    # Здесь загрузить спецификации всех монет
    resp = requests.get(
        "https://api-demo.bybit.com/v5/market/instruments-info",
        params={"category": "linear", "limit": 1000},
        timeout=10,
    ).json()

    # Собираем filters: symbol -> {qtyStep, minOrderQty}
    filters = {}
    for item in resp["result"]["list"]:
        lot = item["lotSizeFilter"]
        filters[item["symbol"]] = {
            "qtyStep": float(lot["qtyStep"]),
            "minOrderQty": float(lot["minOrderQty"]),
        }

    # Словарь трейдеров (изначально пустой)
    traders = {}

    # Первый запуск сразу
    run(traders, filters)

    t = INTERVALS_TO_SEC[INTERVAL]
    while True:
        now = time.time()
        # print(f"\n{time.ctime(now)} | След. в: {time.ctime(now + t - now % t + 1)}")
        # time.sleep(t - now % t + 0.1)
        run(traders, filters)

if __name__ == "__main__":
    timer()
