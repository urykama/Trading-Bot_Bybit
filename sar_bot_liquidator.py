# sar_bot_liquidator.py
# Бот-самоубийца: инвертированный SAR, без стопа, x10, маржа 5% депо на сделку.
# Цель: на длинной истории гарантированно слить депозит (отрицательное EV + тяжёлый хвост убытков).
# Адаптирован под обвязку ApiBybit / тест-биржу.

import time
import pandas as pd

from calculator_sar import calculate_sar
from api_bybit import ApiBybit

# ========== НАСТРОЙКИ ==========
mode_sandbox = True
if mode_sandbox != True:
    api = ApiBybit()
else:
    api = ApiBybit(base_url="http://127.0.0.1:8000")

INTERVAL = '1m'
LEVERAGE = 10  # плечо x10
MARGIN_PCT = 0.05  # 5% депозита как маржа на сделку
# номинал позиции = депозит * MARGIN_PCT * LEVERAGE = 50% депозита
INTERVALS_TO_SEC = {
    '1m': 60, '3m': 180, '5m': 300, '15m': 900, '30m': 1800,
    '1h': 3600, '2h': 7200, '4h': 14400, '1d': 86400,
}
STEPS = {"100.0": 0, "10.0": 0, "1.0": 0, "0.1": 1, "0.01": 2,
         "0.001": 3, "0.0001": 4, "0.00001": 5}


def fetch_klines(pair, limit=128):
    resp = api.fetch_klines(pair, interval=INTERVAL, limit=limit)
    raw = resp["result"]["list"]
    if not raw:
        return None
    df = pd.DataFrame(raw, columns=["time", "open", "high", "low", "close", "volume", "turnover"]).astype(float)
    df = df.drop(columns=["turnover"])
    if df['time'].iloc[0] > df['time'].iloc[-1]:
        df = df.iloc[::-1].reset_index(drop=True)
    return df


"""class LiquidatorTrader:
    def __init__(self, pair, qty_step, min_order_qty, balance):
        self.pair = pair
        self.qty_step = qty_step
        self.min_order_qty = min_order_qty
        self.decimal_places = STEPS[str(self.qty_step)]
        self.balance = balance  # текущий баланс (обновляется извне по PnL)
        self.position = None
        self.order_new = {'symbol': pair, 'triggerPrice': 0.0, 'triggerDirection': 0,
                          'side': None, 'qty': None, 'order_id': None}
        self.order_cur = dict(self.order_new)

    def format_qty(self, quantity):
        quantity = max((quantity // self.qty_step) * self.qty_step, self.min_order_qty)
        return f"{quantity:.{self.decimal_places}f}"

    def place_trigger(self):
        order_id = api.set_trigger_order(self.order_new)
        if order_id:
            if self.order_cur['side'] is not None:
                api.cancel_order(self.order_cur)
            self.order_cur = self.order_new.copy()
            self.order_cur['order_id'] = order_id
            return True
        return False

    def process(self, pos):
        df = fetch_klines(self.pair)
        if df is None:
            return
        df = calculate_sar(df)

        # --- синхронизация позиции ---
        if self.position is None or self.position != pos:
            print(f"[{self.pair}] позиция: {self.position} -> {pos}")
            self.position = pos
            api.cancel_all_orders(self.pair)

        # если позиции нет — нечего делать (первый вход делает внешний сигнал/вручную)
        if self.position is None:
            return

        # --- сигнал: инвертированный SAR ---
        # SAR растёт (классика: тренд вверх, покупаем) -> мы ПРОДАЁМ
        side = 'Sell' if (df['sar'].iloc[-1] - df['sar_prev'].iloc[-1]) > 0 else 'Buy'
        trigger_price = df['sar'].iloc[-1]

        # --- размер: маржа 5% депо, номинал = balance * 5% * 10 = 50% депо ---
        notional = self.balance * MARGIN_PCT * LEVERAGE
        qty = notional / trigger_price

        # один ордер на разворот: закрыть текущую + открыть новую
        qty_total = abs(self.position['positionAmt']) + qty

        self.order_new['side'] = side
        self.order_new['triggerPrice'] = trigger_price
        self.order_new['qty'] = self.format_qty(qty_total)
        self.order_new['triggerDirection'] = 2 if trigger_price < df['close'].iloc[-1] else 1

        self.place_trigger()
"""

"""
class LiquidatorTrader:
    def __init__(self, pair, qty_step, min_order_qty, balance):
        self.pair = pair
        self.qty_step = qty_step
        self.min_order_qty = min_order_qty
        self.decimal_places = STEPS[str(self.qty_step)]
        self.balance = balance
        self.position = None
        self.last_signal = None  # <--- Запоминаем последний сигнал

    def format_qty(self, quantity):
        quantity = max((quantity // self.qty_step) * self.qty_step, self.min_order_qty)
        return f"{quantity:.{self.decimal_places}f}"

    def process(self, pos):
        df = fetch_klines(self.pair)
        if df is None:
            return

        # --- СИГНАЛ: Пересечение SMA (без SAR) ---
        # Если SMA10 > SMA20 -> Buy, иначе -> Sell
        sma_fast = df['close'].rolling(window=10).mean().iloc[-1]
        sma_slow = df['close'].rolling(window=20).mean().iloc[-1]

        signal = 'Buy' if sma_fast > sma_slow else 'Sell'

        # --- СИНХРОНИЗАЦИЯ С БИРЖЕЙ ---
        if self.position != pos:
            # print(f"[{self.pair}] Синхронизация: {self.position} -> {pos}")
            self.position = pos

        # Если сигнал не изменился с прошлого раза — ничего не делаем
        if self.last_signal == signal:
            return

        self.last_signal = signal

        # --- РАСЧЕТ РАЗМЕРА (фиксированный) ---
        # Берем текущую цену для расчета
        current_price = df['close'].iloc[-1]
        notional = self.balance * MARGIN_PCT * LEVERAGE
        qty_str = self.format_qty(notional / current_price)

        print(f"[{self.pair}] Новый сигнал: {signal}. Текущая поз: {self.position}")

        # --- ИСПОЛНЕНИЕ (БЕЗ НАКОПЛЕНИЯ) ---

        # 1. Если есть позиция — закрываем её полностью
        if self.position is not None:
            close_side = 'Sell' if self.position['side'] == 'LONG' else 'Buy'
            close_qty = self.format_qty(abs(self.position['positionAmt']))
            print(f"  -> Закрываем {self.position['side']} {close_qty} @ market")
            api.place_market_order(self.pair, close_side, close_qty, reduce_only=True)
            self.position = None  # Обнуляем локально, чтобы не закрыть дважды

        # 2. Открываем новую позицию
        print(f"  -> Открываем {signal} {qty_str} @ market")
        api.place_market_order(self.pair, signal, qty_str, reduce_only=False)
"""


class LiquidatorTrader:
    def __init__(self, pair, qty_step, min_order_qty, balance):
        self.pair = pair
        self.qty_step = qty_step
        self.min_order_qty = min_order_qty
        self.decimal_places = STEPS[str(self.qty_step)]
        self.balance = balance
        self.position = None
        self.last_signal = None

    def format_qty(self, quantity):
        quantity = max((quantity // self.qty_step) * self.qty_step, self.min_order_qty)
        return f"{quantity:.{self.decimal_places}f}"

    def process(self, pos):
        df = fetch_klines(self.pair)
        if df is None or len(df) < 20:
            return

        sma_fast = df['close'].rolling(window=10).mean().iloc[-1]
        sma_slow = df['close'].rolling(window=20).mean().iloc[-1]
        current_price = df['close'].iloc[-1]

        signal = 'Buy' if sma_fast > sma_slow else 'Sell'

        # Синхронизация
        if self.position != pos:
            self.position = pos

        # 1. ПРОВЕРКА: Есть ли у нас позиция, и совпадает ли она с сигналом?
        if self.position is not None:
            current_side = 'Buy' if self.position['side'] == 'LONG' else 'Sell'

            if current_side == signal:
                # Позиция правильная, сигнал не менялся. Просто ждем.
                return
            else:
                # СИГНАЛ РАЗВЕРНУЛСЯ! Мы ОБЯЗАНЫ закрыть позицию.
                # Никаких "оставить якорь", если это мешает развороту.
                # Если нужен якорь для обвязки, закрываем всё, КРОМЕ min_qty.
                close_side = 'Sell' if self.position['side'] == 'LONG' else 'Buy'
                pos_amt = abs(self.position['positionAmt'])
                close_qty = pos_amt - self.min_order_qty

                if close_qty >= self.min_order_qty:
                    print(f"  -> Сигнал развернулся! Принудительно закрываем {self.format_qty(close_qty)}")
                    api.place_market_order(self.pair, close_side, self.format_qty(close_qty), reduce_only=True)
                    # Локально обновляем
                    if self.position['side'] == 'LONG':
                        self.position['positionAmt'] = self.min_order_qty
                    else:
                        self.position['positionAmt'] = -self.min_order_qty

                # После этого мы в "кэше" (с якорем). Идем дальше к фильтру.

        # 2. ФИЛЬТР ДИСТАНЦИИ (работает ТОЛЬКО для открытия новых позиций)
        dist = abs(current_price - sma_slow) / sma_slow * 100
        if dist > 1.5:
            print(f"  -> Дистанция {dist:.2f}% > 1.5%. Сигнал есть, но вход пропускаем.")
            return

        # 3. ОТКРЫТИЕ НОВОЙ ПОЗИЦИИ
        notional = self.balance * MARGIN_PCT * LEVERAGE
        target_qty = notional / current_price

        # Учитываем якорь
        add_qty = target_qty
        if self.position is not None:
            pos_side = 'Buy' if self.position['side'] == 'LONG' else 'Sell'
            if pos_side == signal:
                add_qty = target_qty - abs(self.position['positionAmt'])

        if add_qty > 0:
            print(f"  -> Открываем {signal} {self.format_qty(add_qty)} @ market")
            api.place_market_order(self.pair, signal, self.format_qty(add_qty), reduce_only=False)


# ========== ОБВЯЗКА ==========

def parse_positions(resp):
    out = {}
    for pos in resp["result"]["list"]:
        if float(pos["size"]) != 0:
            out[pos["symbol"]] = {
                "side": "LONG" if pos["side"] == "Buy" else "SHORT",
                "entry_price": float(pos["avgPrice"]),
                "positionAmt": float(pos["size"]),
            }
    return out


def build_lot_size_restrictions():
    resp = api.instruments_info()
    if resp is None:
        return None
    out = {}
    for item in resp["result"]["list"]:
        lot = item["lotSizeFilter"]
        out[item["symbol"]] = {"qtyStep": float(lot["qtyStep"]),
                               "minOrderQty": float(lot["minOrderQty"])}
    return out


def get_balance():
    # под тест-биржу: если есть api.get_balance() — использовать его
    try:
        resp = api.get_balance()
        return float(resp["result"]["list"][0]["walletBalance"])
    except Exception:
        return 1000.0  # fallback для тест-биржи


def timer():
    restrictions = None
    while restrictions is None:
        restrictions = build_lot_size_restrictions()
        if restrictions is None:
            print("ждём биржу...")
            time.sleep(10)

    balance = get_balance()
    traders = {}
    t = INTERVALS_TO_SEC[INTERVAL]

    while True:
        resp = api.get_current_positions()
        if resp is None or resp.get("retCode") != 0:
            print("пропуск тика")
            time.sleep(5)
            continue

        open_positions = parse_positions(resp)
        balance = get_balance()

        # синхронизация трейдеров
        for pair in list(traders):
            if pair not in open_positions:
                del traders[pair]
        for pair, _ in open_positions.items():
            if pair not in traders:
                traders[pair] = LiquidatorTrader(pair,
                                                 restrictions[pair]["qtyStep"],
                                                 restrictions[pair]["minOrderQty"],
                                                 balance)

        for pair, trader in list(traders.items()):
            try:

                trader.process(open_positions.get(pair))
            except Exception as e:
                print(f"ошибка {pair}: {e}")

        # на реальной бирже ждём границу свечи; в песочнице крутимся сразу
        if mode_sandbox != True:
            now = time.time()
            time.sleep(t - now % t + 3)


if __name__ == "__main__":
    timer()
