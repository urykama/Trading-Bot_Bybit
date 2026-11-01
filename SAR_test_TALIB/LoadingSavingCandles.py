# LoadingSavingCandles.py
import os
import pandas as pd
import time

# def load_klines(symbol, interval, folder='Candles'):
#     """
#     Загружает свечи из файла
#     """
#     print(f'Загружаю файл {symbol}_{interval}.csv')
#     path = os.path.join(folder, f"{symbol}_{interval}.csv")
#     path = "5m.csv"
#
#     if not os.path.exists(path):
#         print(f"Файл {path} не найден")
#         return None
#
#     df = pd.read_csv(path)
#     # df['timestamp'] = pd.to_datetime(df['timestamp'])
#     return df


import os
import pandas as pd
import time
from binance import Binance


def fetch_klines(symbol, interval, limit=500, start_time=None, end_time=None):
    """
    Загружает свечи с биржи
    """
    client = Binance()
    params = {'symbol': symbol, 'interval': interval, 'limit': limit}
    if start_time:
        params['startTime'] = start_time
    if end_time:
        params['endTime'] = end_time

    data = client.klines(**params)

    if not data:
        print(f"Нет данных для {symbol} {interval}")
        return None

    df = pd.DataFrame(data, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_asset_volume', 'trades',
        'taker_base', 'taker_quote', 'ignore'
    ])
    df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].copy()
    # df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)

    return df


def fetch_all_klines(symbols, intervals, limit=500):
    """
    Загружает свечи для всех символов и интервалов
    """
    os.makedirs('Candles', exist_ok=True)

    for symbol in symbols:
        for interval in intervals:
            print(f"\nЗагрузка {symbol} {interval}...")

            # Проверяем, есть ли уже файл
            path = f"Candles/{symbol}_{interval}.csv"
            if os.path.exists(path):
                print(f"  Файл уже существует, пропускаем")
                continue

            try:
                df = fetch_klines(symbol, interval, limit=limit)
                if df is not None and len(df) > 0:
                    df.to_csv(path, index=False)
                    print(f"  Сохранено {len(df)} свечей")
                else:
                    print(f"  Нет данных")
                time.sleep(0.5)  # пауза чтобы не банили
            except Exception as e:
                print(f"  Ошибка: {e}")


def load_klines(symbol, interval, folder='Candles'):
    """
    Загружает свечи из файла
    """
    path = os.path.join(folder, f"{symbol}_{interval}.csv")

    if not os.path.exists(path):
        print(f"Файл {path} не найден")
        return None

    df = pd.read_csv(path)
    # df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df


if __name__ == '__main__':
    # Список для тестирования
    # symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT']
    # intervals = ['5m', '1h', '4h', '1d']
    # symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'AINUSDT', 'A2ZUSDT', 'MAGMAUSDT']
    symbols = ['LSKUSDT']
    # intervals = ['5m', '15m', '1h', '4h']
    intervals = ['1m']

    # Загружаем все данные
    fetch_all_klines(symbols, intervals, limit=256)

    # Проверяем загрузку
    print("\n" + "=" * 50)
    print("Проверка загруженных файлов:")
    print("=" * 50)

    for symbol in symbols:
        for interval in intervals:
            df = load_klines(symbol, interval)
            if df is not None:
                print(f"{symbol} {interval}: {len(df)} свечей, "
                      f"от {df['timestamp'].min()} до {df['timestamp'].max()}")
