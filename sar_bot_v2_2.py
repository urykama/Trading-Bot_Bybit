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
INTERVAL = '1m'  # Таймфрейм по умолчанию
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
        self.orderSide = None
        self.entry_price = 0
        self.positionAmt = 0
        self.trigger_order_id = None
        self.trigger_price = 0
        self.df = None

    # def get_reversal_price(self):
    #     """Получает цену разворота из сигнала"""
    #     intervals = find_intervals(self.df)
    #     reversals = get_reversal_info(intervals)
    #     if not reversals:
    #         return None
    #
    #     # Ищем разворотный сигнал (противоположный текущей позиции)
    #     for rev in reversed(reversals):
    #         if (self.orderSide == 'SELL' and rev['direction'] == 'SHORT') or \
    #                 (self.orderSide == 'BUY' and rev['direction'] == 'LONG'):
    #             return rev['price']
    #     return None

    def get_reversal_signals(self):
        """Возвращает список сигналов (цена, тип)"""
        intervals = find_intervals(self.df)
        reversals = get_reversal_info(intervals)
        if not reversals:
            return []

        result = []
        for rev in reversals:
            # Проверяем, подходит ли сигнал для текущей позиции
            if (self.orderSide == 'SELL' and rev['direction'] == 'SHORT') or \
                    (self.orderSide == 'BUY' and rev['direction'] == 'LONG'):
                result.append({
                    'price': rev['price'],
                    'type': rev['type']
                })
        return result

    def place_trigger(self, trigger_price, is_add=False):
        if self.trigger_price == trigger_price:
            return False

        # self.bot.CancelAllOrders(symbol=self.pair)

        current_price = self.df['close'].iloc[-1]

        if is_add:
            # Усреднение: добавляем к текущей позиции столько же
            quantity = abs(self.positionAmt)
        else:
            # Разворот: текущая позиция + новая
            quantity = abs(self.positionAmt) + self.base_usdt / current_price

        order_id = set_trigger_order(self.bot, self.pair, self.orderSide, trigger_price, quantity)
        if order_id:
            self.trigger_order_id = order_id
            self.trigger_price = trigger_price
            # print(f"    ✓ [{self.pair}] {'УСРЕДНЕНИЕ' if is_add else 'РАЗВОРОТ'} {self.orderSide} @ {trigger_price:.2f}, кол-во: {quantity:.4f}")
            return True
        return False

    def process(self, df, pos_data):
        """Основная логика обработки пары"""
        # 1. Обновляем данные позиции из pos_data
        self.orderSideRev = 'SELL' if pos_data['side'] == 'LONG' else 'BUY'
        self.orderSide = 'SELL' if pos_data['side'] == 'SHORT' else 'BUY'
        self.entry_price = pos_data['entry_price']
        self.positionAmt = pos_data['positionAmt']

        # 2. Расчёт SAR
        self.df = calculate_sar(df)

        # 3. Интервалы SAR
        intervals = find_intervals(self.df)
        # 4. Список сигналов разворота
        direction, use_start, prev_start, prev_end, curr_start, curr_end = get_reversal_info(intervals)
        # 5. Пока удаляем все ордера
        self.bot.CancelAllOrders(symbol=self.pair)

        if pos_data['side'] != direction:
            # print("pos_data['side'] == reversals[0]['direction'] ", pos_data['side'] == direction)
            # print(pos_data['side'], direction)
            if use_start == True:
                # Усреднение
                # print(f'1 из 2 ордеров: {abs(self.positionAmt) + self.base_usdt / curr_end} монет по {curr_end}')
                order_id = set_trigger_order(
                    self.bot,
                    self.pair,
                    self.orderSide,
                    curr_end,  # trigger_price,
                    self.base_usdt / curr_end)

                # Разворот
                # print(f'2 из 2 ордеров: {abs(self.positionAmt) + self.base_usdt / curr_start} монет по {curr_start}')
                order_id = set_trigger_order(
                    self.bot,
                    self.pair,
                    self.orderSideRev,
                    curr_start,
                    abs(self.positionAmt) * 2 + self.base_usdt / curr_start)
            else:
                # Разворот
                # print(f'1 ордер: {abs(self.positionAmt) + self.base_usdt / curr_end} монет по {curr_end}')
                order_id = set_trigger_order(
                    self.bot,
                    self.pair,
                    self.orderSideRev,
                    curr_end,  # trigger_price,
                    abs(self.positionAmt) + self.base_usdt / curr_end)

        # Если позиция LONG == SAR LONG
        if pos_data['side'] == direction:
            # print(f'Разворотный ордер: {abs(self.positionAmt) + self.base_usdt / curr_end} монет по {prev_start}')
            # Разворот
            rev_price = prev_end
            if (direction == 'LONG' and self.entry_price > prev_end) or (direction == 'SHORT' and self.entry_price < prev_end):
                rev_price = prev_start
            order_id = set_trigger_order(
                self.bot,
                self.pair,
                self.orderSideRev,
                rev_price,
                abs(self.positionAmt) + self.base_usdt / prev_end)

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
