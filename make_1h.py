# ========== СБОРКА ЧАСОВЫХ СВЕЧЕЙ ИЗ 5-МИНУТНЫХ ==========

def update_5m(df_5m, new_5m):
    """
    Добавляет новые 5м-свечи в df_5m.
    - отсев дублей по time
    - проверка на пропуски (300000 мс между соседними)
    Возвращает обновлённый df_5m.
    """
    if new_5m is None or len(new_5m) == 0:
        return df_5m

    last_time = df_5m['time'].iloc[-1]
    new_5m = new_5m[new_5m['time'] > last_time]

    if len(new_5m) == 0:
        return df_5m

    df_5m = pd.concat([df_5m, new_5m], ignore_index=True)

    # проверка на пропуски
    diffs = df_5m['time'].diff().dropna()
    gaps = diffs[diffs != 300000]
    if len(gaps) > 0:
        print(f"  ⚠ Пропуски в 5м-свечах: {len(gaps)} шт.")

    return df_5m


def make_1h(df_5m):
    """
    Схлопывает 5м-свечи в часовые.
    Берёт только time / open / high / low / close.
    """
    df = df_5m[['time', 'open', 'high', 'low', 'close']].copy()

    # начало часа в мс
    df['hour'] = (df['time'] // 3600000) * 3600000

    df_1h = df.groupby('hour').agg(
        time=('hour', 'first'),
        open=('open', 'first'),
        high=('high', 'max'),
        low=('low', 'min'),
        close=('close', 'last'),
    ).reset_index(drop=True)

    return df_1h