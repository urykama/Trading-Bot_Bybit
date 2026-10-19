# sar_strategy.py
from pprint import pprint

import pandas as pd
# import talib
import numpy as np
from datetime import datetime
import os
# import matplotlib.pyplot as plt
from Parabolic_SAR import calculate_parabolic_sar


# def calculate_sar(df, accel=0.02, max_accel=0.2):
#     """Расчёт SAREXT"""
#     # df['sar_signed'] = talib.SAREXT(df['high'].values, df['low'].values,
#     #                                 startvalue=0, offsetonreverse=0,
#     #                                 accelerationinitlong=accel, accelerationlong=accel, accelerationmaxlong=max_accel,
#     #                                 accelerationinitshort=accel, accelerationshort=accel, accelerationmaxshort=max_accel
#     #                                 )
#     # df['sar_signed'] = pd.Series(df['sar_signed'], index=df.index)
#     # df['sar_level'] = df['sar_signed'].abs()
#     df = calculate_parabolic_sar(df)
#     return df


def find_intervals(df):
    """Находит интервалы SAR"""
    df = df.copy()
    df['direction'] = df['sar_signed'].apply(lambda x: 'SHORT' if x > 0 else 'LONG')
    df['group'] = np.where(df['direction'] != df['direction'].shift(), 1, 0).cumsum()

    intervals = []
    for group, data in df.groupby('group'):
        intervals.append({
            'direction': data['direction'].iloc[0],
            'start_price': data['close'].iloc[0],
            'end_price': data['close'].iloc[-1],
            'start_sar': data['sar_level'].iloc[0],
            'end_sar': data['sar_level'].iloc[-1],
            'start_time': data['timestamp'].iloc[0],  # ← добавить
            'end_time': data['timestamp'].iloc[-1],  # ← добавить
            'length': len(data),
        })
    return intervals


def get_reversal_info(intervals):
    """Возвращает список сигналов разворота с временем"""
    reversals = []
    for i in range(1, len(intervals)):
        if intervals[i]['direction'] == intervals[i - 1]['direction']:
            continue

        # Проверка условия переноса
        curr, prev = intervals[i], intervals[i - 1]
        dist_own = abs(curr['end_sar'] - curr['start_sar'])
        dist_prev = abs(curr['end_sar'] - prev['end_sar'])
        use_start = dist_own < dist_prev

        print(curr['start_sar'], curr['end_sar'], prev['end_sar'])
        print(f"sar_trend_start = {curr['start_sar']} "
              f"SAR = {curr['end_sar']}, "
              f"sar в конце предыдущего тренда = {prev['end_sar']}")

        price = curr['start_sar'] if use_start else curr['end_sar']
        rev_time = curr['start_time'] if use_start else curr['end_time']  # ← добавить время

        reversals.append({
            'direction': intervals[i]['direction'],
            'price': price,
            'time': rev_time,  # ← добавить
            'use_start': use_start,
            'index': i,
            'interval': intervals[i]
        })
    return reversals
