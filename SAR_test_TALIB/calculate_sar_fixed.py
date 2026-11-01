import pandas as pd
import talib
import numpy as np
from LoadingSavingCandles import load_klines


def calculate_sar_first(high, low, close, acceleration=0.02, maximum=0.2):
    sar = [0.0] * len(close)

    # Инициализация (как в оригинале)
    sar[0] = 0
    ep = high[0] if sar[0] == low[0] else low[0]  # оригинал: ep[0] = high[0] if sar[0]==low[0] else low[0]
    af = acceleration
    trend = 1 if sar[0] == low[0] else -1  # оригинал: trend[0] = 1 if sar[0]==low[0] else -1

    for i in range(1, len(close)):
        if trend == 1:
            # SAR по формуле
            sar[i] = sar[i - 1] + af * (ep - sar[i - 1])

            # Ограничение
            if i >= 2:
                sar[i] = min(sar[i], low[i - 1], low[i - 2])
            else:
                sar[i] = min(sar[i], low[i - 1])

            # Разворот?
            if low[i] < sar[i]:
                trend = -1
                # Особый расчет SAR при развороте
                sar[i] = max(high[i], ep)
                # sar[i] = ep
                ep = low[i]
                af = acceleration
            else:
                # Продолжение тренда
                if high[i] > ep:
                    ep = high[i]
                    af = min(af + acceleration, maximum)

        else:  # trend == -1
            # SAR по формуле
            sar[i] = sar[i - 1] + af * (ep - sar[i - 1])

            # Ограничение
            if i >= 2:
                sar[i] = max(sar[i], high[i - 1], high[i - 2])
            else:
                sar[i] = max(sar[i], high[i - 1])

            # Разворот?
            if high[i] > sar[i]:
                trend = 1
                # Особый расчет SAR при развороте
                sar[i] = min(low[i], ep)
                ep = high[i]
                af = acceleration
            else:
                # Продолжение тренда
                if low[i] < ep:
                    ep = low[i]
                    af = min(af + acceleration, maximum)

    return sar


def calculate_sar_second(high, low, close, acceleration=0.02, maximum=0.20):
    initial_af = acceleration
    max_af = maximum
    af_increment = acceleration

    uptrend = close[0] < close[1]

    sar = [low[0] if uptrend else high[0]]
    af = [initial_af]
    ep = [high[0] if uptrend else low[0]]

    for i in range(1, len(close)):
        # предварительный SAR
        candidate = sar[i - 1] + af[i - 1] * (ep[i - 1] - sar[i - 1])

        # проверка разворота
        if (uptrend and candidate > low[i]) or (not uptrend and candidate < high[i]):
            # --- РАЗВОРОТ ---
            uptrend = not uptrend

            # SAR = EP предыдущего тренда, без клэмпа (как в TA-Lib)
            sar.append(ep[i - 1])

            af.append(initial_af)
            ep.append(high[i] if uptrend else low[i])
        else:
            # --- ПРОДОЛЖЕНИЕ ---
            # клэмп по low[i-1], low[i] (лонг) / high[i-1], high[i] (шорт)
            if uptrend:
                candidate = min(candidate, low[i - 1], low[i])
            else:
                candidate = max(candidate, high[i - 1], high[i])
            sar.append(candidate)

            # обновление AF / EP
            if (uptrend and high[i] > ep[i - 1]) or (not uptrend and low[i] < ep[i - 1]):
                af.append(min(max_af, af[i - 1] + af_increment))
                ep.append(high[i] if uptrend else low[i])
            else:
                af.append(af[i - 1])
                ep.append(ep[i - 1])

    return sar


def compare_sar(symbol, interval):
    """Сравнение трёх вариантов расчёта SAR"""
    df = load_klines(symbol, interval, folder='Candles')
    if df is None:
        print(f"Нет данных для {symbol} {interval}")
        return

    high = df['high'].values
    low = df['low'].values
    close = df['close'].values

    # 1. talib.SAR
    sar_talib = talib.SAR(high, low, acceleration=0.02, maximum=0.2)

    # 2. Первый код (сложный)
    sar_first = calculate_sar_first(high, low, close)

    # 3. Второй код (простой)
    sar_second = calculate_sar_second(high, low, close)

    # Сравнение (первые 50 значений, где есть все данные)
    print(f"\n{'=' * 80}")
    print(f"Сравнение SAR для {symbol} {interval}")
    print(f"{'=' * 80}")
    print(
        f"{'Index':<6} {'High':<8} {'Low':<8} {'Close':<10} {'talib':<10} {'First':<10} {'talib-First':<12}")
    print(f"{'-' * 80}")

    for i in range(min(10, len(df))):
        if i < len(sar_talib) and i < len(sar_first) and i < len(sar_second):
            t = sar_talib[i] if not np.isnan(sar_talib[i]) else 0
            f = sar_first[i] if sar_first[i] is not None else 0
            s = sar_second[i] if i < len(sar_second) else 0

            diff1 = t - f
            diff2 = t - s

            # print(f"{i:<6} {high[i]:<8.2f} {low[i]:<8.2f} {close[i]:<8.2f} {t:<10.2f} {f:<10.2f} {s:<10.2f} {diff1:<12.4f} {diff2:<12.4f}")
            print(f"{i:<6} {high[i]:<8.2f} {low[i]:<8.2f} {close[i]:<10.2f} {t:<10.2f} {f:<10.2f} {diff1:<12.4f}")

    # Статистика различий
    diffs_first = []
    diffs_second = []
    for i in range(len(df)):
        if i < len(sar_talib) and i < len(sar_first) and i < len(sar_second):
            if not np.isnan(sar_talib[i]) and sar_first[i] is not None:
                diffs_first.append(abs(sar_talib[i] - sar_first[i]))
                diffs_second.append(abs(sar_talib[i] - sar_second[i]))

    print(f"\nСтатистика отличий от talib.SAR:")
    print(f"  Первый код: среднее отклонение = {np.mean(diffs_first):.4f}, макс = {np.max(diffs_first):.4f}")
    print(f"  Второй код: среднее отклонение = {np.mean(diffs_second):.4f}, макс = {np.max(diffs_second):.4f}")

    # Количество совпадающих знаков направления
    match_first = 0
    match_second = 0
    total = 0

    for i in range(len(df)):
        if i < len(sar_talib) and i < len(sar_first) and i < len(sar_second):
            if not np.isnan(sar_talib[i]) and sar_first[i] is not None:
                dir_talib = 1 if sar_talib[i] < close[i] else -1
                dir_first = 1 if sar_first[i] < close[i] else -1
                dir_second = 1 if sar_second[i] < close[i] else -1

                if dir_talib == dir_first:
                    match_first += 1
                if dir_talib == dir_second:
                    match_second += 1
                total += 1

    print(f"\nСовпадение направления (SAR выше/ниже цены):")
    print(f"  Первый код: {match_first}/{total} ({match_first / total * 100:.1f}%)")
    print(f"  Второй код: {match_second}/{total} ({match_second / total * 100:.1f}%)")


if __name__ == "__main__":
    # Тестируем на ETH-USDT 1h
    compare_sar('ETH-USDT', '1h')

'''
Статистика отличий от talib.SAR:
  Первый код: среднее отклонение = 6.0395, макс = 64.7378
  Второй код: среднее отклонение = 1.4426, макс = 61.4900

Совпадение направления (SAR выше/ниже цены):
  Первый код: 286/299 (95.7%)
  Второй код: 293/299 (98.0%)
'''
