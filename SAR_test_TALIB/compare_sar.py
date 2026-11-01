# compare_sar.py
"""
Сравнение Parabolic SAR: TA-Lib vs sar_calculator.py

1) Загружает свечи из 5m.csv
2) Считает SAR через TA-Lib (SAREXT)
3) Считает SAR через ваш sar_calculator.calculate_sar
4) Строит интерактивный график Plotly: свечи + оба SAR + разница
"""

import pandas as pd
import numpy as np
import talib
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from calculator_sar_copy_talib import calculate_sar_copy_talib as calc_sar_custom

pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)


# ----------------------------------------------------------------------
# 1. Загрузка данных
# ----------------------------------------------------------------------
def load_candles(path: str = "5m.csv") -> pd.DataFrame:
    df = pd.read_csv(path)
    return df


# ----------------------------------------------------------------------
# 2. SAR через TA-Lib
# ----------------------------------------------------------------------
def calc_sar_talib(df: pd.DataFrame,
                   accel: float = 0.02,
                   max_accel: float = 0.2) -> pd.DataFrame:
    """SAREXT -> sar_signed (со знаком), sar_level (модуль)."""
    sar_signed = talib.SAREXT(
        df["high"].values, df["low"].values,
        startvalue=0, offsetonreverse=0,
        accelerationinitlong=accel, accelerationlong=accel, accelerationmaxlong=max_accel,
        accelerationinitshort=accel, accelerationshort=accel, accelerationmaxshort=max_accel,
    )
    df = df.copy()
    df["sar_talib_signed"] = sar_signed
    df["sar_talib_level"] = np.abs(sar_signed)
    return df


# ----------------------------------------------------------------------
# 3. SAR через ваш sar_calculator.py
# ----------------------------------------------------------------------
def calc_sar_custom_wrap(df: pd.DataFrame) -> pd.DataFrame:
    """Обёртка над вашим calculate_sar -> приводит к тем же колонкам, что и TA-Lib."""
    df = calc_sar_custom(df.copy())
    df["sar_custom_level"] = df["sar"]
    df["sar_custom_signed"] = df["sar"] * np.sign(df["trend"]).astype(int)
    return df


# ----------------------------------------------------------------------
# 4. График Plotly
# ----------------------------------------------------------------------
def plot_comparison(df: pd.DataFrame, max_points: int = 500):
    """
    Строит 2 панели:
      - сверху: свечи + TA-Lib SAR + ваш SAR
      - снизу: разница (custom - talib) по уровню SAR
    """
    d = df.tail(max_points).reset_index(drop=True)

    # Ось X
    x = d["time"] if "time" in d.columns else d.index

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        row_heights=[0.75, 0.25],
        vertical_spacing=0.03,
        subplot_titles=("Свечи + Parabolic SAR (TA-Lib vs custom)",
                        "Разница уровней SAR (custom − TA-Lib)"),
    )

    # --- Свечи ---
    fig.add_trace(go.Candlestick(
        x=x, open=d["open"], high=d["high"], low=d["low"], close=d["close"],
        name="Цена",
        increasing_line_color="#26a69a", decreasing_line_color="#ef5350",
    ), row=1, col=1)

    # --- TA-Lib SAR ---
    fig.add_trace(go.Scatter(
        x=x, y=d["sar_talib_level"],
        mode="markers",
        marker=dict(size=6, color="royalblue", symbol="cross"),  # вертикальный крест «+»
        name="SAR TA-Lib",
    ), row=1, col=1)

    # --- Ваш SAR ---
    fig.add_trace(go.Scatter(
        x=x, y=d["sar_custom_level"],
        mode="markers",
        marker=dict(size=6, color="orange", symbol="x"),  # диагональный крест «×»
        name="SAR custom",
    ), row=1, col=1)

    # --- Разница ---
    diff = d["sar_custom_level"] - d["sar_talib_level"]
    fig.add_trace(go.Scatter(
        x=x, y=diff,
        mode="lines",
        line=dict(color="purple", width=1),
        name="custom − talib",
    ), row=2, col=1)

    # Нулевая линия
    fig.add_hline(y=0, line_dash="dash", line_color="gray", row=2, col=1)

    fig.update_layout(
        height=900,
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        template="plotly_white",
        title="Parabolic SAR: TA-Lib vs собственный расчёт",
    )
    fig.update_yaxes(title_text="Цена", row=1, col=1)
    fig.update_yaxes(title_text="Δ SAR", row=2, col=1)

    return fig


# ----------------------------------------------------------------------
# main
# ----------------------------------------------------------------------
def main():
    # 1) Загрузка
    df = load_candles("5m.csv")
    # df = load_candles("5m_up.csv")
    print(f"Загружено свечей: {len(df)}")
    print(df.head())

    # 2) TA-Lib
    df = calc_sar_talib(df)

    # 3) Custom
    df = calc_sar_custom_wrap(df)

    # 4) Статистика расхождения
    diff = (df["sar_custom_level"] - df["sar_talib_level"]).abs()
    print("\n=== Расхождение custom vs TA-Lib ===")
    print(f"max |Δ|  : {diff.max():.6f}")
    print(f"mean |Δ| : {diff.mean():.6f}")
    print(f"кол-во строк с |Δ| > 1e-9: {(diff > 1e-9).sum()}")

    # ---------------------------------------------------------------
    # Детальная диагностика расхождений
    # ---------------------------------------------------------------
    diff = df["sar_custom_level"] - df["sar_talib_level"]
    bad_idx = df.index[np.abs(diff) > 1e-9]

    print(f"\n=== Детальная диагностика (найдено расхождений: {len(bad_idx)}) ===")
    if len(bad_idx) == 0:
        print("Полное совпадение с TA-Lib (в пределах 1e-9).")
    else:
        print(f"{'i':<5} {'timestamp':<20} {'open':<10} {'high':<10} {'low':<10} {'close':<10} "
              f"{'talib':<12} {'custom':<12} {'diff':<12} ")
        print("-" * 130)

        for i in bad_idx:
            row = df.loc[i]
            # trend и ep есть только в кастомном df

            t = row["sar_talib_level"]
            c = row["sar_custom_level"]
            d = c - t

            time_val = row["time"] if "time" in row.index else str(i)
            # print(f"{i:<5} {str(time_val):<20} "
            print(f"{i:<5} {row['timestamp']:<20} "
                  f"{row['open']:<10.4f} {row['high']:<10.4f} {row['low']:<10.4f} {row['close']:<10.4f} "
                  f"{t:<12.4f} {c:<12.4f} {d:<12.4f} ")

    # 5) График
    fig = plot_comparison(df, max_points=500)
    fig.write_html("sar_comparison.html", include_plotlyjs="cdn")
    fig.show()
    print("\nГрафик сохранён в sar_comparison.html")
    print(df)


if __name__ == "__main__":
    main()
