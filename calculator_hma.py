# calculator_hma.py
"""
Hull Moving Average (HMA) по Алану Халлу.

Считает HMA и производные:
    hma       — Hull Moving Average
    hma_speed — скорость (изменение HMA на шаг)
    hma_accel — ускорение (изменение скорости на шаг)

Использование:
    from calculator_hma import calculate_hma
    df = calculate_hma(df, period=14)

Требования к DataFrame:
    - колонка 'close'
"""

import numpy as np
import pandas as pd


def wma(series, period):
    """
    Взвешенная скользящая средняя (WMA).

    Веса: 1, 2, ..., period (последнее значение имеет наибольший вес).
    Реализовано через sliding_window_view + матричное умножение,
    без rolling().apply и без lambda.
    """
    if period < 1:
        raise ValueError(f"period must be >= 1, got {period}")

    values = series.to_numpy(dtype=float)
    n = len(values)
    result = np.full(n, np.nan, dtype=float)

    if n < period:
        return pd.Series(result, index=series.index)

    weights = np.arange(1, period + 1, dtype=float)
    weights /= weights.sum()

    windows = np.lib.stride_tricks.sliding_window_view(values, period)
    result[period - 1:] = windows @ weights

    return pd.Series(result, index=series.index)


def calculate_hma(df, period=16):
    """
    HMA по Алану Халлу + скорость и ускорение от HMA.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame с колонкой 'close'.
    period : int
        Период HMA (по умолчанию 14).

    Returns
    -------
    df : pd.DataFrame
        Тот же DataFrame с добавленными колонками:
            hma       — Hull Moving Average
            hma_speed — скорость (изменение HMA на шаг)
            hma_accel — ускорение (изменение скорости на шаг)

    Notes
    -----
    Для корректного расчёта нужно минимум
        half + period + sqrt_n - 2
    строк, где half = period // 2, sqrt_n = int(sqrt(period)).
    Иначе первые значения (и, возможно, весь ряд) будут NaN.
    """

    # df_hma = df.iloc[-33:-1]  # 32 строки, последняя отброшена
    df_hma = df.iloc[-33:]  # 32 строки, последняя отброшена
    if period < 2:
        raise ValueError(f"period must be >= 2, got {period}")

    n = period
    half = int(n / 2)
    sqrt_n = int(np.sqrt(n))

    wma1 = wma(df_hma['close'], half)
    wma2 = wma(df_hma['close'], n)
    raw_hma = 2 * wma1 - wma2
    df_hma['hma'] = wma(raw_hma, sqrt_n)

    df_hma['hma_speed'] = df_hma['hma'].diff(1)
    df_hma['hma_accel'] = df_hma['hma_speed'].diff(1)

    return df_hma
