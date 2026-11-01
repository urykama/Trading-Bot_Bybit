# sar_calculator.py
"""
Parabolic SAR Calculator (Wilder).

Модуль для расчёта Parabolic SAR по Уайлдеру.
Возвращает 5 массивов:
  - sar_start: SAR в начале свечи (до проверки касания) — для триггеров
  - sar:       SAR после проверки (может измениться внутри свечи)
  - ep:        Extreme Point (максимум/минимум с начала тренда)
  - sar_prev:  SAR перед последним разворотом
  - trend:     + восходящий, - нисходящий, число длина тренда (количество свечей)

  - (не реализовано) sar_trend_start   значение SAR на первой свече нового тренда (то есть в момент разворота,
   когда SAR пересчитывается через EP предыдущего тренда

Использование:
    from sar_calculator import calculate_sar
    sar_start, sar, ep, sar_prev, trend = calculate_sar(df)



Требования к DataFrame:
  - колонки: 'high', 'low', 'close'
  - индекс: 0, 1, 2, ... (стандартный)
"""

import pandas as pd
import numpy as np


def calculate_sar_copy_talib(df):
    """
    Parabolic SAR как в TA-Lib (почти).
    Ограничение SAR предыдущими экстремумами.
    В TA-Lib есть защита «SAR не должен входить в диапазон предыдущей/текущей свечи»
    Parameters
    ----------
    df : pd.DataFrame
        DataFrame с колонками 'high', 'low', 'close'.

    Returns
    -------
    sar_start : list[float]
        меняем название на sar_before_touch
        SAR в начале свечи (до проверки касания).
    sar : list[float]
        SAR после проверки (может измениться внутри свечи).
    ep : list[float]
        Extreme Point.
    sar_prev : list[float]
        SAR перед последним разворотом.
    trend : list[int]
        + — восходящий, - — нисходящий, число длина тренда (количество свечей)


    """

    # === Стандартные параметры SAR ===
    initial_af = 0.02  # начальный acceleration factor
    max_af = 0.20  # максимальный AF
    af_increment = 0.02  # шаг увеличения AF

    # === Определяем начальный тренд ===
    uptrend = df['close'][0] < df['close'][1]

    # === Инициализация первого бара ===
    sar_before_touch = [df['low'][1] if uptrend else df['high'][1]]
    sar = [df['low'][1] if uptrend else df['high'][1]]

    af = [initial_af]
    ep = [df['high'][0] if uptrend else df['low'][0]]

    # sar_prev — SAR перед последним разворотом
    sar_prev = [sar[0]]
    sar_trend_start = [sar[0]]
    # trend — направление тренда
    trend = [1 if uptrend else -1]
    trend_len = 1
    # === Основной цикл ===
    for i in range(1, len(df)):

        # 1. Рассчитываем SAR на текущей свече (предварительно)
        # Ограничение SAR предыдущими экстремумами.
        # В TA-Lib есть защита «SAR не должен входить в диапазон предыдущей/текущей свечи»
        candidate = sar[i - 1] + af[i - 1] * (ep[i - 1] - sar[i - 1])
        if i > 1:
            if uptrend:
                candidate = min(candidate, df['low'][i - 2], df['low'][i - 1])
            else:
                candidate = max(candidate, df['high'][i - 2], df['high'][i - 1])
        sar_before_touch.append(candidate)

        # 2. Проверяем разворот тренда
        if (uptrend and sar_before_touch[i] > df['low'][i]) or (not uptrend and sar_before_touch[i] < df['high'][i]):

            # Разворот
            uptrend = not uptrend
            trend_len = 1
            # SAR пересчитывается через EP предыдущего тренда
            sar.append(min(ep[i - 1], df['low'][i]) if uptrend else max(ep[i - 1], df['high'][i]))
            # SAR = EP предыдущего тренда (без клэмпа!)
            # sar.append(ep[i - 1])
            # AF сбрасывается, EP обновляется
            af.append(initial_af)
            ep.append(df['high'][i] if uptrend else df['low'][i])

            # sar_prev = SAR перед разворотом
            sar_prev.append(sar[i - 1])
            sar_trend_start.append(sar[i])

        else:
            trend_len += 1
            # Предварительный SAR + клэмп
            candidate = sar_before_touch[i]

            sar.append(candidate)

            # Обновляем AF и EP при новом экстремуме
            if (uptrend and df['high'][i] > ep[i - 1]) or (not uptrend and df['low'][i] < ep[i - 1]):
                af.append(min(max_af, af[i - 1] + af_increment))
                ep.append(df['high'][i] if uptrend else df['low'][i])
            else:
                af.append(af[i - 1])
                ep.append(ep[i - 1])

            # sar_prev не меняется
            sar_prev.append(sar_prev[i - 1])
            sar_trend_start.append(sar_trend_start[i - 1])

        # 3. Записываем тренд для текущей свечи
        trend.append(trend_len * (1 if uptrend else -1))

    df['sar_prev'] = sar_prev
    df['sar_trend_start'] = sar_trend_start
    df['sar_before_touch'] = sar_before_touch
    df['sar'] = sar
    df['ep'] = ep
    df['trend'] = trend
    return df


"""
🎯 Как использовать

python

# main.py

import pandas as pd
from sar_calculator import calculate_sar

sar_start, sar, ep, sar_prev, trend = calculate_sar(df)

df['sar_start'] = sar_start
df['sar'] = sar
df['ep'] = ep
df['sar_prev'] = sar_prev
df['trend'] = trend


if i == 0:
    trend_length = 1
else:
    if (uptrend and trend[i-1] > 0) or (not uptrend and trend[i-1] < 0):
        trend_length = abs(trend[i-1]) + 1   # продолжаем
    else:
        trend_length = 1                     # новый тренд

trend.append(trend_length if uptrend else -trend_length)
"""
