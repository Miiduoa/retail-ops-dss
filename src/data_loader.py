# -*- coding: utf-8 -*-
"""資料載入與基本檢查。"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "retail_daily_sales.csv"


def load_sales(path: Path | None = None) -> pd.DataFrame:
    """載入日銷量 CSV；若不存在則自動呼叫產生腳本。"""
    p = path or DATA_PATH
    if not p.exists():
        # 延遲匯入，避免循環依賴
        import runpy

        gen = ROOT / "generate_data.py"
        runpy.run_path(str(gen), run_name="__main__")
    df = pd.read_csv(p, encoding="utf-8-sig")
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["store_id", "category_id", "date"]).reset_index(drop=True)
    return df


def list_stores(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df[["store_id", "store_name", "region"]]
        .drop_duplicates()
        .sort_values("store_id")
        .reset_index(drop=True)
    )


def list_categories(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df[["category_id", "category_name"]]
        .drop_duplicates()
        .sort_values("category_id")
        .reset_index(drop=True)
    )
