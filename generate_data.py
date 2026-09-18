#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
合成零售日銷量資料產生器
一鍵執行：python generate_data.py
產生可重現（固定種子）的多門市 × 多品類日銷量，供決策支援原型使用。
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd

# 固定種子，確保備審 Demo 可重現
SEED = 42
OUT_PATH = Path(__file__).resolve().parent / "data" / "retail_daily_sales.csv"

STORES = [
    {"store_id": "S01", "store_name": "台北信義店", "region": "北區", "base_traffic": 1.25},
    {"store_id": "S02", "store_name": "台中逢甲店", "region": "中區", "base_traffic": 1.10},
    {"store_id": "S03", "store_name": "高雄夢時代店", "region": "南區", "base_traffic": 1.00},
    {"store_id": "S04", "store_name": "新竹科學園區店", "region": "北區", "base_traffic": 0.95},
]

CATEGORIES = [
    {"category_id": "C01", "category_name": "飲料", "base_demand": 120, "price_mean": 45, "promo_lift": 0.35},
    {"category_id": "C02", "category_name": "零食", "base_demand": 90, "price_mean": 55, "promo_lift": 0.45},
    {"category_id": "C03", "category_name": "鮮食", "base_demand": 70, "price_mean": 80, "promo_lift": 0.25},
    {"category_id": "C04", "category_name": "日用品", "base_demand": 50, "price_mean": 120, "promo_lift": 0.20},
]


def _taiwan_holiday_flags(dates: pd.DatetimeIndex) -> np.ndarray:
    """簡化假日標記：週末 + 常見國定假日（固定月日近似）。"""
    holiday_md = {
        (1, 1),
        (2, 28),
        (4, 4),
        (4, 5),
        (5, 1),
        (10, 10),
        (12, 25),
    }
    flags = np.zeros(len(dates), dtype=int)
    for i, d in enumerate(dates):
        if d.weekday() >= 5:
            flags[i] = 1
        if (d.month, d.day) in holiday_md:
            flags[i] = 1
    return flags


def generate(n_days: int = 730, start: str = "2023-01-01") -> pd.DataFrame:
    """產生 n_days 天、多門市 × 多品類的日銷量合成資料。"""
    rng = np.random.default_rng(SEED)
    dates = pd.date_range(start=start, periods=n_days, freq="D")
    holiday = _taiwan_holiday_flags(dates)
    rows = []

    for store in STORES:
        for cat in CATEGORIES:
            # 門市 × 品類專屬噪音與趨勢
            store_cat_noise = rng.normal(0, 0.08)
            trend = rng.uniform(0.0001, 0.0006)  # 緩慢成長
            seasonal_amp = rng.uniform(0.08, 0.18)

            for i, d in enumerate(dates):
                dow = d.weekday()
                # 週末效應
                weekend_lift = 1.25 if dow >= 5 else 1.0
                # 週內節奏（週五較高）
                dow_factor = 1.0 + (0.12 if dow == 4 else 0.0) - (0.08 if dow == 0 else 0.0)
                # 年季節（夏日飲料、歲末零食等簡化）
                doy = d.dayofyear
                season = 1.0 + seasonal_amp * np.sin(2 * np.pi * (doy - 80) / 365)
                if cat["category_id"] == "C01":  # 飲料夏高
                    season *= 1.0 + 0.15 * np.sin(2 * np.pi * (doy - 150) / 365)
                if cat["category_id"] == "C02" and d.month in (1, 12):
                    season *= 1.15

                # 促銷（約 12% 天數）
                is_promo = int(rng.random() < 0.12)
                promo_factor = 1.0 + cat["promo_lift"] if is_promo else 1.0

                # 價格波動
                price = cat["price_mean"] * (1.0 + rng.normal(0, 0.05))
                if is_promo:
                    price *= 0.85
                price_elasticity = -0.35
                price_factor = (price / cat["price_mean"]) ** price_elasticity

                holiday_factor = 1.30 if holiday[i] else 1.0

                mu = (
                    cat["base_demand"]
                    * store["base_traffic"]
                    * (1 + store_cat_noise)
                    * (1 + trend * i)
                    * weekend_lift
                    * dow_factor
                    * season
                    * promo_factor
                    * price_factor
                    * holiday_factor
                )
                # 負二項近似：以 Poisson 加超離散
                sales = max(0, int(rng.poisson(max(mu, 1)) + rng.normal(0, max(mu * 0.05, 1))))

                # 庫存與人力相關欄位（供決策建議使用）
                inventory = int(max(0, sales * rng.uniform(1.5, 3.5) + rng.normal(20, 5)))
                staff_hours = round(4 + sales / 40 + (2 if holiday[i] or dow >= 5 else 0) + rng.normal(0, 0.5), 1)

                rows.append(
                    {
                        "date": d.strftime("%Y-%m-%d"),
                        "store_id": store["store_id"],
                        "store_name": store["store_name"],
                        "region": store["region"],
                        "category_id": cat["category_id"],
                        "category_name": cat["category_name"],
                        "sales_qty": sales,
                        "unit_price": round(price, 1),
                        "is_promo": is_promo,
                        "is_holiday": int(holiday[i]),
                        "day_of_week": dow,
                        "inventory_end": inventory,
                        "staff_hours": max(3.0, staff_hours),
                    }
                )

    df = pd.DataFrame(rows)
    df = df.sort_values(["store_id", "category_id", "date"]).reset_index(drop=True)
    return df


def main() -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df = generate()
    df.to_csv(OUT_PATH, index=False, encoding="utf-8-sig")
    print(f"已寫入：{OUT_PATH}")
    print(f"列數：{len(df):,}｜日期範圍：{df['date'].min()} ~ {df['date'].max()}")
    print(f"門市：{df['store_name'].nunique()}｜品類：{df['category_name'].nunique()}")
    print(df.head(3).to_string(index=False))


if __name__ == "__main__":
    main()
