# -*- coding: utf-8 -*-
"""可解釋性：特徵重要性與類似歷史日對照。"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .features import FEATURE_COLS


def top_feature_importance(importance_df: pd.DataFrame, top_k: int = 8) -> pd.DataFrame:
    return importance_df.head(top_k).copy()


FEATURE_LABELS_ZH = {
    "lag_1": "前一日銷量",
    "lag_7": "七日前銷量",
    "lag_14": "十四日前銷量",
    "roll_mean_7": "近7日均量",
    "roll_mean_14": "近14日均量",
    "roll_std_7": "近7日波動",
    "day_of_week": "星期幾",
    "is_weekend": "是否週末",
    "is_holiday": "是否假日",
    "is_promo": "是否促銷",
    "unit_price": "單價",
    "month": "月份",
    "day_of_month": "日",
}


def labelize(importance_df: pd.DataFrame) -> pd.DataFrame:
    out = importance_df.copy()
    out["特徵"] = out["feature"].map(lambda x: FEATURE_LABELS_ZH.get(x, x))
    out["重要性"] = out["importance"]
    return out[["特徵", "重要性", "feature"]]


def similar_history_days(
    hist: pd.DataFrame,
    target_dow: int,
    is_promo: int,
    top_n: int = 5,
) -> pd.DataFrame:
    """找出與目標情境相近的歷史日（同星期、促銷狀態接近），供解釋對照。"""
    h = hist.dropna(subset=["sales_qty"]).copy()
    if h.empty:
        return h
    score = (h["day_of_week"] == target_dow).astype(int) * 2 + (
        h["is_promo"] == is_promo
    ).astype(int)
    h = h.assign(_sim=score).sort_values(["_sim", "date"], ascending=[False, False])
    cols = ["date", "sales_qty", "is_promo", "is_holiday", "unit_price", "day_of_week"]
    return h[cols].head(top_n).reset_index(drop=True)
