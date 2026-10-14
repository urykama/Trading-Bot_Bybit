# sar_bot.py
from pprint import pprint

import pandas as pd
import time
import requests
# from BingX_demo_250605 import BingX
from sar_strategy import (
    calculate_sar,
    find_intervals,
    get_reversal_info,
)
from bybit_api import API_Bybit

# ========== НАСТРОЙКИ ==========
BASE_USDT = 200  # Базовый размер позиции в USDT
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
    "1": 0,
    "0.1": 1,
    "0.01": 2,
    "0.001": 3,
    "0.0001": 4,
    "0.00001": 5,
    "0.000001": 6,
    "0.0000001": 7,
    "0.00000001": 8,
}

api = API_Bybit()


# ========== КЛАСС ТОРГОВОГО БОТА ДЛЯ ОДНОЙ ПАРЫ ==========
class SARTrader:

    def __init__(self, pair, qty_step, min_order_qty):

        self.pair = pair
        self.qty_step = qty_step
        self.min_order_qty = min_order_qty
        self.base_usdt = BASE_USDT
        self.position_amt = None
        self.position_ep = None
        self.position_side = None
        self.last_loss = False
        self.trigger_order_id = None
        self.trigger_price = 0
        self.last_trigger_price = 0
        self.pending_trigger = False
        self.entry_direction = None
        self.side = None

        print(f"  Трейдер создан для {pair}: шаг количества {qty_step}, минимальный размер ордера {min_order_qty}")

    def get_base_quantity(self, price):
        """Возвращает базовое количество монет на self.base_usdt"""
        return self.base_usdt / price

    def sync_with_exchange(self, position):
        """Синхронизирует состояние с биржей"""

        new_position = 1 if position['side'] == 'LONG' else -1
        if new_position != self.position_side:
            print(f"  [{self.pair}] Позиция изменилась на бирже: {self.position_side} -> {new_position}")
            self.position_side = new_position
            self.position_ep = position['entry_price']
            self.position_amt = position['positionAmt']
            # Сбрасываем триггер
            self.trigger_order_id = None
            self.trigger_price = 0
            self.last_trigger_price = 0
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
            api.cancel_all_orders(self.pair)
            # print(f"  [{self.pair}] Удалены старые триггеры")
        except Exception as e:
            print(f"  [{self.pair}] Ошибка удаления: {e}")

        # Ставим новый
        order_id = api.set_trigger_order(self.pair, self.side, trigger_price, quantity)
        if order_id:
            self.trigger_order_id = order_id
            self.trigger_price = trigger_price
            self.last_trigger_price = trigger_price
            self.pending_trigger = True
            # print(f"  ✓ [{self.pair}] Триггер {self.entry_direction} {self.side} @ {trigger_price:.2f}, кол-во: {quantity:.4f}")
            return True
        return False

    def prepare(self, df):
        # Определяем направление разворота
        if self.position_side == 1:
            self.entry_direction = 'SHORT'
            self.side = 'Sell'
        elif self.position_side == -1:
            self.entry_direction = 'LONG'
            self.side = 'Buy'

        df = calculate_sar(df)
        df = df.dropna(subset=['sar_signed'])
        if len(df) < 2:
            return None

        intervals = find_intervals(df)
        reversals = get_reversal_info(intervals)
        if not reversals:
            return None

        return {"df": df, "reversals": reversals}

    def decide(self, prepared):
        # 2.1. Ищем актуальный разворотный сигнал (противоположный текущей позиции)
        new_trigger_price = None
        for rev in reversed(prepared['reversals']):
            if (self.position_side == 1 and rev['direction'] == 'SHORT') or \
                    (self.position_side == -1 and rev['direction'] == 'LONG'):
                # 2.2 Получаем новую цену триггера из сигнала
                new_trigger_price = rev['price']
                break
        # 2.3. Выбираем лучшую цену (сравниваем с текущей, если триггер уже стоит)
        best_price = self.get_best_trigger_price(new_trigger_price)
        return best_price

    def execute(self, best_price):
        """Ставит/обновляет триггер по принятому решению."""

        # 7. Проверяем, нужно ли обновлять триггер
        need_update = False
        if not self.pending_trigger:
            # Триггера нет — нужно поставить
            need_update = True
        elif self.trigger_price != best_price:
            # Цена изменилась — нужно обновить
            self.trigger_price = best_price
            need_update = True
            # print(f"          [{self.pair}] Цена триггера изменилась: {self.trigger_price:.2f} -> {best_price:.2f}")

        # 8. Если нужно обновить — ставим новый триггер
        if need_update:
            quantity = abs(self.position_amt) + self.base_usdt / best_price
            # quantity = 0.008
            print(quantity, "\t=\t", self.base_usdt, "\t/\t", best_price)
            # Округление qty до qtyStep и проверка minOrderQty
            quantity = max((quantity // self.qty_step) * self.qty_step, self.min_order_qty)
            n = STEPS[str(self.qty_step)]
            quantity = f"{quantity:.{n}f}"
            self.place_trigger(best_price, quantity)
        else:
            # Триггер уже существует с оптимальной ценой — ничего не делаем
            if self.pending_trigger:
                pass  # можно добавить отладочный вывод при необходимости

    def process(self, df, pos):
        # 1.1. Синхронизация с биржей
        self.sync_with_exchange(pos)
        if not self.position_side:
            return False

        prepared = self.prepare(df)
        if prepared is None:
            return True

        new_trigger_price = self.decide(prepared)
        if new_trigger_price is None:
            return True

        self.execute(new_trigger_price)
        return True


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
            df = api.fetch_klines(pair)
            if df is None:
                continue

            # Трейдер решает, оставлять ли его дальше
            # should_keep = trader.process(df, open_positions)
            should_keep = trader.process(df, open_positions.get(pair))
            if not should_keep:
                del traders[pair]
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

    restrictions = {}
    for item in resp["result"]["list"]:
        lot = item["lotSizeFilter"]
        restrictions[item["symbol"]] = {
            "qtyStep": float(lot["qtyStep"]),
            "minOrderQty": float(lot["minOrderQty"]),
        }
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
