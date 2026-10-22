# sar_bot.py

import time
import requests
from pprint import pprint

import pandas as pd

from calculator_sar import calculate_sar
from calculator_hma import calculate_hma

from api_bybit import api_bybit

# ========== НАСТРОЙКИ ==========
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)
BASE_USDT = 200  # Базовый размер позиции в USDT
# INTERVAL = '1m'  # Таймфрейм по умолчанию
INTERVAL = '5m'  # Таймфрейм по умолчанию
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

api = api_bybit()


class KlineError(Exception):
    pass


def resp_to_df(resp):
    """... None — если предпоследняя свеча не является последней закрытой на 'сейчас'."""
    raw = resp["result"]["list"]
    df = pd.DataFrame(
        raw,
        columns=["time", "open", "high", "low", "close", "volume", "turnover"],
    ).astype(float)
    df = df.drop(columns=["turnover"])
    if df['time'].iloc[0] > df['time'].iloc[-1]:
        df = df.iloc[::-1].reset_index(drop=True)

    df = df.iloc[:-1].reset_index(drop=True)

    interval_ms = INTERVALS_TO_SEC[INTERVAL] * 1000
    now_ms = time.time() * 1000
    new_last_start = int(df["time"].iloc[-1])
    if not (new_last_start + interval_ms <= now_ms < new_last_start + 2 * interval_ms):
        raise KlineError("resp_to_df: предпоследняя свеча не является последней закрытой")
    return df


def resp_to_df_incremental(resp):
    """resp от api.fetch_klines -> df без незакрытой последней свечи (если она есть).
    Не проверяет актуальность — это делает merge/continuity в load_klines_incremental."""
    raw = resp["result"]["list"]
    df = pd.DataFrame(
        raw,
        columns=["time", "open", "high", "low", "close", "volume", "turnover"],
    ).astype(float)
    df = df.drop(columns=["turnover"])
    if df['time'].iloc[0] > df['time'].iloc[-1]:
        df = df.iloc[::-1].reset_index(drop=True)

    interval_ms = INTERVALS_TO_SEC[INTERVAL] * 1000
    now_ms = time.time() * 1000
    last_start = int(df["time"].iloc[-1])
    if last_start + interval_ms > now_ms:
        df = df.iloc[:-1].reset_index(drop=True)
    return df


# ========== КЛАСС ТОРГОВОГО БОТА ДЛЯ ОДНОЙ ПАРЫ ==========
class SARTrader:

    def __init__(self, pair, qty_step, min_order_qty):

        self.pair = pair
        self.qty_step = qty_step
        self.min_order_qty = min_order_qty
        self.decimal_places = STEPS[str(self.qty_step)]
        self.base_usdt = BASE_USDT
        self.position = None
        self.df = None

        self.pnl_expected = 0
        self.pnl_total = 0
        self.order_new = {
            'symbol': self.pair,
            'triggerPrice': 0.0,
            'triggerDirection': 0,
            'side': None,
            'qty': None,
            'order_id': None,
        }
        self.order_cur = {
            'symbol': self.pair,
            'triggerPrice': 0.0,
            'triggerDirection': 0,
            'side': None,
            'qty': None,
            'order_id': None,
        }
        print(f"  Трейдер создан для {pair}: шаг количества {qty_step}, минимальный размер ордера {min_order_qty}")

    def place_trigger(self):

        # Удаляем старые триггеры
        # try:
        #     api.cancel_all_orders(self.pair)
        #     # print(f"  [{self.pair}] Удалены старые триггеры")
        # except Exception as e:
        #     print(f"  [{self.pair}] Ошибка удаления: {e}")

        print(f"             ствавим ордер: {self.order_new}")
        # Ставим новый ордер
        order_id = api.set_trigger_order(self.order_new)

        if order_id:
            print(f"             ордер удачно установлен, order_id = {order_id}")
            if self.order_cur['side'] != None:
                resp = api.cancel_order(self.order_cur)
            # print(f"             ордер c order_id = {self.order_cur['order_id']} deleted: {resp}")
            self.order_cur = self.order_new.copy()
            self.order_cur['order_id'] = order_id

            return True
        return False

    def calculate_price(self, df):
        # print(f"                        df['sar_prev'].iloc[-1] = {df['sar_prev'].iloc[-1]}")
        # print(f"df['sar'].iloc[-1 - abs(df['trend'].iloc[-1])]] = {df['sar'].iloc[- 1 - abs(df['trend'].iloc[-1])]}")
        # print(
        #     f"df['sar'].iloc[-1 - abs(df['trend'].iloc[-1])]] = {df['sar_before_touch'].iloc[- abs(df['trend'].iloc[-1])]}")

        # dist_own = abs(df['sar'].iloc[-1] - df['sar_trend_start'].iloc[-1])
        # dist_prev = abs(df['sar'].iloc[-1] - df['sar_prev'].iloc[-1])
        # use_start = dist_own < dist_prev

        # new_trigger_price = df['sar_trend_start'].iloc[-1] if use_start else df['sar'].iloc[-1]
        best_price = df['sar'].iloc[-1]

        if (self.position['side'] == 'SHORT' and best_price < df['close'].iloc[-1]) or (
                self.position['side'] == 'LONG' and best_price > df['close'].iloc[-1]):
            best_price = df['sar_prev'].iloc[-1]

        self.order_new['triggerPrice'] = best_price
        return

    def format_qty(self, quantity):
        """Округление до qtyStep, проверка minOrderQty, формат строки под биржу."""
        quantity = max((quantity // self.qty_step) * self.qty_step, self.min_order_qty)
        return f"{quantity:.{self.decimal_places}f}"

    def calculate_pnl(self):
        # print(f"delta_price = self.order_new['triggerPrice'] - self.position['entry_price']")
        if self.position['side'] == 'LONG':
            delta_price = self.order_new['triggerPrice'] - self.position['entry_price']
            # print(f"{delta_price} = {self.order_new['triggerPrice']} - {self.position['entry_price']}")
        else:
            delta_price = self.position['entry_price'] - self.order_new['triggerPrice']
            # print(f"{delta_price} = {self.position['entry_price']} - {self.order_new['triggerPrice']}")
        self.pnl_expected = delta_price * self.position['positionAmt']

        # print(f"self.pnl_expected = {self.pnl_expected} \t self.pnl_total = {self.pnl_total}")
        self.base_usdt = BASE_USDT - (self.pnl_total + self.pnl_expected) * 50
        if self.base_usdt < BASE_USDT:
            self.base_usdt = BASE_USDT
            self.pnl_total = 0

    def load_klines_initial(self, limit=128):
        resp = api.fetch_klines(self.pair, INTERVAL, limit=limit)
        self.df = resp_to_df(resp)

    def load_klines_incremental(self, safety=2):
        if self.df is None or len(self.df) == 0:
            self.load_klines_initial()
            return

        interval_ms = INTERVALS_TO_SEC[INTERVAL] * 1000
        last_known = int(self.df["time"].iloc[-1])
        start = last_known - safety * interval_ms

        resp = api.fetch_klines(self.pair, INTERVAL, limit=200, start=start)
        df_new = resp_to_df_incremental(resp)

        self.df = (
            pd.concat([self.df, df_new], ignore_index=True)
            .drop_duplicates(subset="time", keep="last")
            .sort_values("time")
            .reset_index(drop=True)
        )

    def process(self, pos):
        # 1.1. Синхронизация с биржей, подготовка данных
        if self.df is None:
            self.load_klines_initial()
        else:
            self.load_klines_incremental()
        df = self.df
        print(df)
        if self.position != pos:
            print(f"\n\t\t\t\t\t\t  [{self.pair}] Позиция изменилась на бирже: {self.position} -> {pos}")
            self.position = pos
            self.pnl_total += self.pnl_expected
        else:
            dh = calculate_hma(df)
            # print(dh)
            print(self.position['side'], dh['hma'].iloc[-3], dh['hma'].iloc[-2], dh['hma'].iloc[-1])
            print(self.position['side'] == 'LONG', dh['hma'].iloc[-3] < dh['hma'].iloc[-2] > dh['hma'].iloc[-1])
            side = 'no side'
            k = 0.8
            # if self.position['side'] == 'Buy' and dh['hma_accel'][-3] < dh['hma_accel'][-2] > dh['hma_accel'][-1] and \
            #         dh['close'][-2] < dh['close'][-1]:
            if (self.position['side'] == 'LONG') and (dh['hma'].iloc[-3] < dh['hma'].iloc[-2] > dh['hma'].iloc[-1]):
                side = 'Sell'
            # elif self.position['side'] == 'Sell' and dh['hma_accel'][-3] > dh['hma_accel'][-2] < dh['hma_accel'][-1] and \
            #         dh['close'][-2] > dh['close'][-1]:
            elif (self.position['side'] == 'SHORT') and (dh['hma'].iloc[-3] > dh['hma'].iloc[-2] < dh['hma'].iloc[-1]):
                side = 'Buy'
            print(f" side = {side} \t side != 'no side' = {side != 'no side'}")
            # side = 'Sell'
            if side != 'no side':
                qty = self.format_qty(abs(self.position['positionAmt']) * 0.382)
                print(80 * "-", self.pair, side, qty)
                order_id = api.place_market_order(self.pair, side, qty)
                print(order_id)

        # df = self.prepare(df)  # вычисление calculate_sar
        df = calculate_sar(df)
        # Принятие решения (поиск цены для триггера)
        # Определяем направление для нового ордера (противоположно текущей позиции
        self.order_new['side'] = 'Sell' if self.position['side'] == 'LONG' else 'Buy'
        # print(f"self.position['side' ] = {self.position['side']} \t\t self.order_new['side'] = {self.order_new['side']}")
        self.calculate_price(df)
        # self.calculate_pnl()
        quantity = abs(self.position['positionAmt']) + self.base_usdt / self.order_new['triggerPrice']
        self.order_new['qty'] = self.format_qty(quantity)
        # self.order_new['triggerDirection'] = 1 if self.order_new['triggerPrice'] > df['close'].iloc[-1] else 2
        self.order_new['triggerDirection'] = 2 if self.position['side'] == 'LONG' else 1

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


def tick(traders, restrictions):
    """Один проход: синхронизация трейдеров с позициями и обработка каждого."""
    resp = api.get_current_positions()
    # 1) транспорт упал — пропускаем тик, НЕ трогаем трейдеров
    if resp is None or resp.get("retCode") != 0:
        print("  Пропуск тика: нет ответа от биржи")
        return
    open_positions = parse_positions(resp)

    sync_traders(traders, open_positions, restrictions)

    process_traders(traders, open_positions)


def build_lot_size_restrictions():
    """Формирует словарь ограничений размера лота: symbol -> {qtyStep, minOrderQty}."""
    resp = api.instruments_info()
    if resp is None:
        return None  # сигнал «не смогли получить»

    restrictions = {}
    # pairs = set()
    for item in resp["result"]["list"]:
        lot = item["lotSizeFilter"]
        restrictions[item["symbol"]] = {
            "qtyStep": float(lot["qtyStep"]),
            "minOrderQty": float(lot["minOrderQty"]),
        }
        # pairs.add((float(lot["qtyStep"]), float(lot["minOrderQty"])))
    # for qty_step, min_qty in sorted(pairs):
    #     print(f"qtyStep={qty_step:<12} minOrderQty={min_qty}")
    return restrictions


def timer():
    """Таймер"""
    restrictions = None
    while restrictions is None:
        restrictions = build_lot_size_restrictions()
        if restrictions is None:
            print("  Ждём биржу, повтор через 10 сек...")
            time.sleep(10)

    traders = {}
    tick(traders, restrictions)

    t = INTERVALS_TO_SEC[INTERVAL]
    while True:
        now = time.time()
        print(time.ctime(now), '\t след. в: ', time.ctime(now + t - now % t + 1), '\t', now % t)
        time.sleep(t - now % t + 3)
        tick(traders, restrictions)


if __name__ == "__main__":
    timer()

"""
{
 'adlRankIndicator': 2,
 'autoAddMargin': 0,
 'avgPrice': '0.004386',
 'breakEvenPrice': '0.00438117',
 'bustPrice': '',
 'createdTime': '1792311126219',
 'cumRealisedPnl': '-110.2144042',
 'curRealisedPnl': '-0.12712821',
 'isReduceOnly': False,
 'leverage': '10',
 'leverageSysUpdatedTime': '',
 'liqPrice': '0.00552364',
 'liqPriceByMp': '',
 'markPrice': '0.0044005',
 'mmrSysUpdatedTime': '',
 'netDeltaRatio': '',
 'openTime': 1792689074250,
 'positionBalance': '0',
 'positionIM': '23.33047603',
 'positionIMByMp': '23.33047603',
 'positionIdx': 0,
 'positionMM': '2.45890453',
 'positionMMByMp': '2.45890453',
 'positionStatus': 'Normal',
 'positionValue': '231.90635',
 'riskId': 1,
 'riskLimitValue': '200000',
 'seq': 140679343654577,
 'sessionAvgPrice': '',
 'side': 'Sell',
 'size': '52700',
 'stopLoss': '',
 'symbol': '1000PEPEUSDT',
 'takeProfit': '',
 'tpslMode': 'Full',
 'tradeMode': 0,
 'trailingStop': '0',
 'unrealisedPnl': '-0.76415',
 'updatedTime': '1792689074250'
 }
"""
"""
Поле	Значение (кратко)
adlRankIndicator	Ранг риска авто-делевериджа (ADL): чем выше, тем вероятнее принудительное сокращение позиции 
autoAddMargin	Авто-добавление маржи в изолированном режиме (0 = выкл) 
avgPrice	Средняя цена входа в позицию 
breakEvenPrice	Цена безубыточности (с учётом комиссий) 
bustPrice	Цена банкротства (когда потеряна вся маржа); пусто = не применимо 
createdTime	Время создания записи позиции (мс)
cumRealisedPnl	Накопленный реализованный PnL за всё время по символу 
curRealisedPnl	Реализованный PnL текущего удержания (с последнего изменения размера) 
isReduceOnly	Флаг «только уменьшение» (при понижении лимита риска биржей) 
leverage	Текущее плечо позиции 
leverageSysUpdatedTime	Время последнего системного изменения плеча (пусто = не менялось)
liqPrice	Цена ликвидации (для кросс-маржи — расчётная) 
liqPriceByMp	Цена ликвидации, рассчитанная по mark price (служебное)
markPrice	Текущая mark price (цена для расчёта PnL/ликвидации) 
mmrSysUpdatedTime	Время системного обновления ставки поддерживающей маржи (пусто = не менялось)
netDeltaRatio	Коэффициент чистого дельта (для опционов/дельта-нейтрального режима); пусто = режим не включён 
openTime	Время открытия текущей позиции (мс)
positionBalance	Баланс позиции (для изолированной маржи; 0 = не применимо/пусто)
positionIM	Начальная маржа (Initial Margin), требуемая для удержания позиции 
positionIMByMp	То же, но рассчитано по mark price (обычно совпадает) 
positionIdx	Идентификатор позиции: 0 = one-way mode 
positionMM	Поддерживающая маржа (Maintenance Margin), минимум для удержания 
positionMMByMp	То же, но по mark price (обычно совпадает) 
positionStatus	Статус: Normal / Liq (ликвидация) / Adl (авто-делеверидж) 
positionValue	Стоимость позиции (size × markPrice) 
riskId	ID уровня риска (тира лимитов) 
riskLimitValue	Значение лимита риска для текущего тира 
seq	Порядковый номер обновления позиции (для отслеживания актуальности)
sessionAvgPrice	Средняя цена сессии (для USDC-контрактов; пусто = не применимо) 
side	Направление: Buy = лонг, Sell = шорт 
size	Размер позиции (всегда положительный) 
stopLoss	Цена стоп-лосса (пусто = не установлен)
symbol	Торговая пара
takeProfit	Цена тейк-профита (пусто = не установлен)
tpslMode	Режим TP/SL: Full (на всю позицию) / Partial
tradeMode	Режим маржи: 0 = кросс, 1 = изолированная 
trailingStop	Дистанция трейлинг-стопа (0 = не установлен)
unrealisedPnl	Нереализованный PnL (плавающая прибыль/убыток) 
updatedTime	Время последнего обновления позиции (мс)
"""
