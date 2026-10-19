# sar_bot_v2_1.py
import time
import pandas as pd
from BingX_demo_250605 import BingX
from sar_strategy import (
    calculate_sar, find_intervals, get_reversal_info,
    set_trigger_order,
    # save_chart
)

# ========== НАСТРОЙКИ ==========
BASE_USDT = 1000  # Базовый размер позиции в USDT
INTERVAL = '1h'  # Таймфрейм по умолчанию
INTERVALS_TO_SEC = {
    '1m': 60, '3m': 180, '5m': 300, '15m': 900, '30m': 1800,
    '1h': 3600, '2h': 7200, '4h': 14400, '1d': 86400,
}


# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
def get_current_positions(bot):
    """Получает открытые позиции с биржи"""
    resp = bot.PositionInfo()
    if resp.get('code') != 0:
        return {}

    positions = {}
    for pos in resp.get('data', []):
        if float(pos.get('positionAmt', 0)) != 0:
            positions[pos['symbol']] = {
                'side': pos['positionSide'],
                'entry_price': float(pos['avgPrice']),
                'positionAmt': float(pos['positionAmt'])
            }
    return positions


def fetch_klines(bot, pair, interval=INTERVAL, limit=128):
    """Загружает свечи с биржи"""
    klines = bot.klines(symbol=pair, interval=interval, limit=limit)
    # print(klines)
    if 'data' not in klines:
        return None

    df = pd.DataFrame(klines['data']).astype(float)
    df.sort_values('time', inplace=True)
    df['timestamp'] = pd.to_datetime(df['time'] * 0.001 + 3600 * 5, unit='s')
    # print(df)
    return df


# ========== КЛАСС ТОРГОВОГО БОТА ДЛЯ ОДНОЙ ПАРЫ ==========
class SARTrader:
    def __init__(self, bot, pair, base_usdt=BASE_USDT):
        self.bot = bot
        self.pair = pair
        self.base_usdt = base_usdt

        # Состояние
        self.position = 0
        self.entry_price = 0
        self.trigger_order_id = None
        self.trigger_price = 0
        self.positionAmt = 0
        self.last_trigger_price = 0
        self.pending_trigger = False
        self.entry_direction = None
        self.side = None
        self.position_size = 1.0

    def get_base_quantity(self, price):
        """Возвращает базовое количество монет на self.base_usdt"""
        return self.base_usdt / price

    def get_trigger_info(self):
        """Возвращает (entry_direction, side) для разворота"""
        if self.position == 1:  # LONG -> разворот в SHORT
            return 'SHORT', 'SELL'
        elif self.position == -1:  # SHORT -> разворот в LONG
            return 'LONG', 'BUY'
        else:
            return None, None

    def get_best_trigger_price(self, new_price):
        """Выбирает лучшую цену триггера"""
        entry_direction, _ = self.get_trigger_info()
        if entry_direction is None:
            return new_price

        if entry_direction == 'LONG':
            candidates = []
            if self.last_trigger_price > 0:
                candidates.append(self.last_trigger_price)
            if new_price > 0:
                candidates.append(new_price)
            if not candidates:
                return new_price
            best = min(candidates)
            if best != self.last_trigger_price and self.last_trigger_price > 0:
                print(f"            [{self.pair}] Цена LONG улучшена: {self.last_trigger_price:.2f} -> {best:.2f}")
            return best
        else:  # SHORT
            candidates = []
            if self.last_trigger_price > 0:
                candidates.append(self.last_trigger_price)
            if new_price > 0:
                candidates.append(new_price)
            if not candidates:
                return new_price
            best = max(candidates)
            if best != self.last_trigger_price and self.last_trigger_price > 0:
                print(f"            [{self.pair}] Цена SHORT улучшена: {self.last_trigger_price:.2f} -> {best:.2f}")
            return best

    def place_trigger(self, trigger_price, quantity):
        """Ставит триггер, если цена изменилась"""
        entry_direction, side = self.get_trigger_info()
        if entry_direction is None:
            print(f"  [{self.pair}] Нет позиции, триггер не ставится")
            return False

        # Проверяем, нужен ли новый ордер
        if self.pending_trigger and self.trigger_price == trigger_price:
            print(f"  [{self.pair}] Триггер уже существует с ценой {trigger_price:.2f}, пропускаем")
            return False

        # Удаляем старые триггеры
        try:
            self.bot.CancelAllOrders(symbol=self.pair)
            print(f"[{self.pair}] Удалены старые триггеры")
        except Exception as e:
            print(f"  [{self.pair}] Ошибка удаления: {e}")

        # Ставим новый
        order_id = set_trigger_order(self.bot, self.pair, side, trigger_price, quantity)
        if order_id:
            self.trigger_order_id = order_id
            self.trigger_price = trigger_price
            self.last_trigger_price = trigger_price
            self.pending_trigger = True
            print(f"    ✓ [{self.pair}] Триггер {entry_direction} {side} @ {trigger_price:.2f}, кол-во: {quantity:.4f}")
            return True
        return False

    def get_reversal_price(self, df):
        """Получает цену разворота из сигнала"""
        intervals = find_intervals(df)
        reversals = get_reversal_info(intervals)
        if not reversals:
            return None

        # Ищем разворотный сигнал (противоположный текущей позиции)
        for rev in reversed(reversals):
            if (self.position == 1 and rev['direction'] == 'SHORT') or \
                    (self.position == -1 and rev['direction'] == 'LONG'):
                return rev['price']
        return None

    def process(self, df, pos_data):
        """Основная логика обработки пары"""
        # 1. Обновляем данные позиции из pos_data
        self.position = 1 if pos_data['side'] == 'LONG' else -1
        self.entry_price = pos_data['entry_price']
        self.positionAmt = pos_data['positionAmt']

        # 2. Расчёт SAR
        df = calculate_sar(df)

        # 3. Получаем цену для разворота
        trigger_price = self.get_reversal_price(df)
        if trigger_price is None:
            return True

        current_price = df['close'].iloc[-1]

        # 4. Выбираем лучшую цену
        best_price = self.get_best_trigger_price(trigger_price)

        # 5. Проверяем, нужно ли обновлять триггер
        need_update = False
        if not self.pending_trigger:
            need_update = True
        elif self.trigger_price != best_price:
            need_update = True
            # print(f"                [{self.pair}] Цена триггера изменилась: {self.trigger_price:.2f} -> {best_price:.2f}")

        # 6. Если нужно — ставим триггер
        if need_update:
            quantity = abs(self.positionAmt) + self.get_base_quantity(current_price)
            self.place_trigger(best_price, quantity)

        return True


# ========== ОСНОВНОЙ ЦИКЛ ==========
def run(bot, traders):
    """Основной цикл"""
    open_positions = get_current_positions(bot)
    # print(open_positions)
    for pair, pos_data in open_positions.items():
        # Создаём трейдера если нет
        if pair not in traders:
            traders[pair] = SARTrader(bot, pair)
            print(f"  Создан трейдер для {pair}")

        try:
            df = fetch_klines(bot, pair)
            if df is None:
                continue
            traders[pair].process(df, pos_data)
        except Exception as e:
            print(f"  Ошибка {pair}: {e}")

def timer():
    """Таймер"""
    t = INTERVALS_TO_SEC[INTERVAL]
    bot = BingX()

    # Словарь трейдеров (изначально пустой)
    traders = {}

    # Первый запуск сразу
    run(bot, traders)

    while True:
        now = time.time()
        print(f"\n{time.ctime(now)} | След. в: {time.ctime(now + t - now % t + 1)}")
        time.sleep(t - now % t + 0.1)
        run(bot, traders)


if __name__ == "__main__":
    timer()
