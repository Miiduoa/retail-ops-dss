# -*- coding: utf-8 -*-
"""特徵工程：滯後、移動統計、日曆與促銷特徵。"""

from __future__ import annotations

import pandas as pd

FEATURE_COLS = [
    "lag_1",
    "lag_7",
    "lag_14",
    "roll_mean_7",
    "roll_mean_14",
    "roll_std_7",
    "day_of_week",
    "is_weekend",
    "is_holiday",
    "is_promo",
    "unit_price",
    "month",
    "day_of_month",
]


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """依門市×品類分組加入時間序列特徵。"""
    out = df.copy()
    out = out.sort_values(["store_id", "category_id", "date"])
    g = out.groupby(["store_id", "category_id"], group_keys=False)

    out["lag_1"] = g["sales_qty"].shift(1)
    out["lag_7"] = g["sales_qty"].shift(7)
    out["lag_14"] = g["sales_qty"].shift(14)
    out["roll_mean_7"] = g["sales_qty"].transform(
        lambda s: s.shift(1).rolling(7, min_periods=3).mean()
    )
    out["roll_mean_14"] = g["sales_qty"].transform(
        lambda s: s.shift(1).rolling(14, min_periods=5).mean()
    )
    out["roll_std_7"] = g["sales_qty"].transform(
        lambda s: s.shift(1).rolling(7, min_periods=3).std()
    )
    out["is_weekend"] = (out["day_of_week"] >= 5).astype(int)
    out["month"] = out["date"].dt.month
    out["day_of_month"] = out["date"].dt.day

    # 缺失以組內中位數填補（開頭滯後期）
    for col in FEATURE_COLS:
        if col in out.columns:
            out[col] = g[col].transform(lambda s: s.fillna(s.median()))
            out[col] = out[col].fillna(0)

    return out


def prepare_xy(df_feat: pd.DataFrame):
    """回傳特徵矩陣與標籤。"""
    X = df_feat[FEATURE_COLS].astype(float)
    y = df_feat["sales_qty"].astype(float)
    return X, y
