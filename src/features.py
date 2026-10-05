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

GROUP_COLS = ["store_id", "category_id"]


def add_features(df: pd.DataFrame, impute: bool = True) -> pd.DataFrame:
    """依門市×品類分組加入時間序列特徵。

    `impute=False` 用於 hold-out 評估：先建立原始 lag／rolling 特徵，
    再由訓練區間估計缺值填補統計，避免測試期資訊回流。
    """
    out = df.copy()
    out = out.sort_values(GROUP_COLS + ["date"])
    g = out.groupby(GROUP_COLS, group_keys=False)

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

    if impute:
        # 全量訓練／實際預測時，資料皆屬已知歷史；以組內中位數填補開頭 lag 缺值。
        g_feat = out.groupby(GROUP_COLS, group_keys=False)
        for col in FEATURE_COLS:
            out[col] = g_feat[col].transform(lambda s: s.fillna(s.median()))
            out[col] = out[col].fillna(0)

    return out


def fit_feature_imputer(df_feat: pd.DataFrame) -> dict:
    """只用傳入資料估計特徵缺值填補統計。"""
    grouped = df_feat.groupby(GROUP_COLS)
    group_medians: dict[str, dict[tuple, float]] = {}
    global_medians: dict[str, float] = {}

    for col in FEATURE_COLS:
        group_medians[col] = grouped[col].median().to_dict()
        global_median = df_feat[col].median()
        global_medians[col] = 0.0 if pd.isna(global_median) else float(global_median)

    return {
        "group_medians": group_medians,
        "global_medians": global_medians,
    }


def apply_feature_imputer(df_feat: pd.DataFrame, imputer: dict) -> pd.DataFrame:
    """套用既有填補統計，不重新從目標資料估計任何值。"""
    out = df_feat.copy()
    keys = list(zip(out["store_id"], out["category_id"]))

    for col in FEATURE_COLS:
        group_map = imputer["group_medians"][col]
        fallback = float(imputer["global_medians"][col])
        fill_values = pd.Series(
            [group_map.get(key, fallback) for key in keys],
            index=out.index,
            dtype=float,
        )
        out[col] = out[col].astype(float).fillna(fill_values).fillna(fallback)

    return out


def prepare_xy(df_feat: pd.DataFrame):
    """回傳特徵矩陣與標籤。"""
    X = df_feat[FEATURE_COLS].astype(float)
    y = df_feat["sales_qty"].astype(float)
    return X, y
