# sar_bot.py

import time
import requests
from pprint import pprint

import pandas as pd

from Parabolic_SAR import calculate_parabolic_sar

from bybit_api import ApiBybit

# ========== НАСТРОЙКИ ==========
BASE_USDT = 200  # Базовый размер позиции в USDT
INTERVAL = '1m'  # Таймфрейм по умолчанию
# INTERVAL = '5m'  # Таймфрейм по умолчанию
# INTERVAL = '1h'  # Таймфрейм по умолчанию
INTERVALS_TO_SEC = {
    '1m': 60, '3m': 180, '5m': 300, '15m': 900, '30m': 1800,
    '1h': 3600, '2h': 7200, '4h': 14400, '1d': 86400,
}

STEPS = {

    "100.0": 0,
    "10.0": 0,
    "1.0": 0,
    "0.1": 1,
    "0.01": 2,
    "0.001": 3,
    "0.0001": 4,
    "0.00001": 5,
}

api = ApiBybit()


# ========== КЛАСС ТОРГОВОГО БОТА ДЛЯ ОДНОЙ ПАРЫ ==========
class SARTrader:

    def __init__(self, pair, qty_step, min_order_qty):

        self.pair = pair
        self.qty_step = qty_step
        self.min_order_qty = min_order_qty
        self.base_usdt = BASE_USDT
        self.position = None
        self.trigger_order_id = None
        self.order_new = {
            'symbol': self.pair,
            'triggerPrice': 0.0,
            'triggerDirection': 0,
            'side': None,
            'qty': None,
        }
        self.order_cur = {
            'symbol': self.pair,
            'triggerPrice': 0.0,
            'triggerDirection': 0,
            'side': None,
            'qty': None,
        }
        print(f"  Трейдер создан для {pair}: шаг количества {qty_step}, минимальный размер ордера {min_order_qty}")

    def place_trigger(self):

        # Удаляем старые триггеры
        try:
            api.cancel_all_orders(self.pair)
            # print(f"  [{self.pair}] Удалены старые триггеры")
        except Exception as e:
            print(f"  [{self.pair}] Ошибка удаления: {e}")

        print(self.order_new)
        # Ставим новый
        order_id = api.set_trigger_order(self.order_new)

        if order_id:
            self.order_cur = self.order_new.copy()
            self.trigger_order_id = order_id
            return True
        return False

    def calculate_price(self, df):
        print(f"                        df['sar_prev'].iloc[-1] = {df['sar_prev'].iloc[-1]}")
        print(f"df['sar'].iloc[-1 - abs(df['trend'].iloc[-1])]] = {df['sar'].iloc[- 1 - abs(df['trend'].iloc[-1])]}")
        print(
            f"df['sar'].iloc[-1 - abs(df['trend'].iloc[-1])]] = {df['sar_before_touch'].iloc[- abs(df['trend'].iloc[-1])]}")

        dist_own = abs(df['sar'].iloc[-1] - df['sar_trend_start'].iloc[-1])
        dist_prev = abs(df['sar'].iloc[-1] - df['sar_prev'].iloc[-1])
        use_start = dist_own < dist_prev

        # new_trigger_price = df['sar_trend_start'].iloc[-1] if use_start else df['sar'].iloc[-1]
        best_price = df['sar'].iloc[-1]

        if (self.position['side'] == 'SHORT' and best_price < df['close'].iloc[-1]) or (
                self.position['side'] == 'LONG' and best_price > df['close'].iloc[-1]):
            best_price = df['sar_prev'].iloc[-1]

        self.order_new['triggerPrice'] = best_price

        return

    def calculate_qty(self):
        """Ставит/обновляет триггер по принятому решению."""
        quantity = abs(self.position['positionAmt']) + self.base_usdt / self.order_new['triggerPrice']
        print(quantity, "\t=\t", self.base_usdt, "\t/\t", self.order_new['triggerPrice'])
        # Округление qty до qtyStep и проверка minOrderQty
        quantity = max((quantity // self.qty_step) * self.qty_step, self.min_order_qty)
        print(f"quantity = {quantity}")
        n = STEPS[str(self.qty_step)]
        print(f"n = {n}")
        self.order_new['qty'] = f"{quantity:.{n}f}"

    def process(self, pos):
        # 1.1. Синхронизация с биржей, подготовка данных
        if self.position != pos:
            print(f"\n\t\t\t\t\t\t  [{self.pair}] Позиция изменилась на бирже: {self.position} -> {pos}")
        self.position = pos

        df = api.fetch_klines(self.pair, INTERVAL)
        # df = self.prepare(df)  # вычисление calculate_parabolic_sar
        df = calculate_parabolic_sar(df)

        # Принятие решения (поиск цены для триггера)
        # Определяем направление для нового ордера (противоположно текущей позиции
        self.order_new['side'] = 'Sell' if self.position['side'] == 'LONG' else 'Buy'
        # print(f"self.position['side'] = {self.position['side']} \t\t self.order_new['side'] = {self.order_new['side']}")
        self.calculate_price(df)
        self.calculate_qty()
        self.order_new['triggerDirection'] = 1 if self.order_new['triggerPrice'] > df['close'].iloc[-1] else 2

        # Исполнение (вычисление количества)
        # self.execute()
        self.place_trigger()


# ========== ОСНОВНОЙ ЦИКЛ ==========

def sync_traders(traders, open_positions, restrictions):
    """Удаляет трейдеров без позиции и создаёт новых для появившихся позиций."""
    # --- Удаляем трейдеров, чьи позиции закрылись ---
    pairs_to_remove = []
    for pair, trader in traders.items():
        if pair not in open_positions:
            print(f"  Позиция {pair} закрыта, удаляем трейдера")
            pairs_to_remove.append(pair)

    for pair in pairs_to_remove:
        del traders[pair]

    # --- Создаём трейдеров для новых позиций ---
    for pair, pos_data in open_positions.items():
        if pair not in traders:
            traders[pair] = SARTrader(
                pair,
                restrictions[pair]["qtyStep"],
                restrictions[pair]["minOrderQty"],  # ограничения размера лота (qtyStep, minOrderQty)
            )


def process_traders(traders, open_positions):
    """Прогоняет каждого трейдера через его логику и удаляет отживших."""
    for pair, trader in list(traders.items()):  # list() — т.к. ниже можем удалять из traders
        try:
            # Трейдер решает, оставлять ли его дальше
            # should_keep = trader.process(df, open_positions)
            trader.process(open_positions.get(pair))
        except Exception as e:
            print(f"  Ошибка {pair}: {e}")


def tick(traders, restrictions):
    """Один проход: синхронизация трейдеров с позициями и обработка каждого."""
    open_positions = api.get_current_positions()
    sync_traders(traders, open_positions, restrictions)
    process_traders(traders, open_positions)


def build_lot_size_restrictions():
    """Формирует словарь ограничений размера лота: symbol -> {qtyStep, minOrderQty}."""
    resp = requests.get(
        "https://api-demo.bybit.com/v5/market/instruments-info",
        params={"category": "linear", "limit": 1000},
        timeout=10,
    ).json()
    print(resp['result']['category'])
    print(resp['result']['nextPageCursor'])

    for text in resp['result']:
        pprint(text)
    restrictions = {}
    pairs = set()
    for item in resp["result"]["list"]:
        lot = item["lotSizeFilter"]
        restrictions[item["symbol"]] = {
            "qtyStep": float(lot["qtyStep"]),
            "minOrderQty": float(lot["minOrderQty"]),
        }
        pairs.add((float(lot["qtyStep"]), float(lot["minOrderQty"])))
    for qty_step, min_qty in sorted(pairs):
        print(f"qtyStep={qty_step:<12} minOrderQty={min_qty}")
    return restrictions


def timer():
    """Таймер"""
    restrictions = build_lot_size_restrictions()

    traders = {}
    tick(traders, restrictions)

    t = INTERVALS_TO_SEC[INTERVAL]
    while True:
        now = time.time()
        print(time.ctime(now), '\t след. в: ', time.ctime(now + t - now % t + 1), '\t', now % t)
        time.sleep(t - now % t + 0.1)
        tick(traders, restrictions)


if __name__ == "__main__":
    timer()
