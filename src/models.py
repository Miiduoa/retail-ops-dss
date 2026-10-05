# -*- coding: utf-8 -*-
"""預測模型：移動平均 baseline + RandomForest；MAE/MAPE 評估與快取。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import zlib

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error

from .features import (
    FEATURE_COLS,
    add_features,
    apply_feature_imputer,
    fit_feature_imputer,
    prepare_xy,
)

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "models"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_PATH = CACHE_DIR / "rf_bundle.joblib"


@dataclass
class EvalResult:
    model_name: str
    mae: float
    mape: float
    n_test: int


def mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    mask = y_true != 0
    if mask.sum() == 0:
        return float("nan")
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100)


def time_split(df: pd.DataFrame, test_days: int = 60):
    """依全域最後 test_days 天切分訓練／測試。"""
    max_date = df["date"].max()
    cut = max_date - pd.Timedelta(days=test_days - 1)
    train = df[df["date"] < cut].copy()
    test = df[df["date"] >= cut].copy()
    return train, test


class MovingAverageBaseline:
    """簡單移動平均 baseline：以過去 window 日均值預測隔日。"""

    def __init__(self, window: int = 7):
        self.window = window
        self.last_values_: dict[tuple, list[float]] = {}

    def fit(self, df: pd.DataFrame) -> "MovingAverageBaseline":
        self.last_values_.clear()
        for key, g in df.groupby(["store_id", "category_id"]):
            vals = g.sort_values("date")["sales_qty"].tolist()
            self.last_values_[key] = vals[-self.window :]
        return self

    def predict_frame(self, df: pd.DataFrame) -> np.ndarray:
        preds = []
        # rolling one-step-ahead：每一天只使用當日前已觀測到的歷史實績。
        history = {k: list(v) for k, v in self.last_values_.items()}
        for _, row in df.sort_values("date").iterrows():
            key = (row["store_id"], row["category_id"])
            hist = history.get(key, [])
            pred = float(np.mean(hist[-self.window :])) if hist else 0.0
            preds.append(pred)
            history[key] = (hist + [float(row["sales_qty"])])[-self.window :]
        order = df.sort_values("date").index
        series = pd.Series(preds, index=order)
        return series.reindex(df.index).to_numpy()


class DemandForecaster:
    """封裝 RF 訓練、評估與多步預測。"""

    def __init__(self, n_estimators: int = 80, max_depth: int = 12, random_state: int = 42):
        self.model = RandomForestRegressor(
            n_estimators=n_estimators,
            max_depth=max_depth,
            min_samples_leaf=3,
            n_jobs=-1,
            random_state=random_state,
        )
        self.baseline = MovingAverageBaseline(window=7)
        self.feature_names_ = FEATURE_COLS
        self.trained_ = False
        self.eval_results_: list[EvalResult] = []
        self.feature_importance_: pd.DataFrame | None = None
        self.history_df_: pd.DataFrame | None = None

    def fit_eval(self, df_raw: pd.DataFrame, test_days: int = 60) -> list[EvalResult]:
        # 先建立未填補的特徵，再時間切分；缺值統計只由訓練區間估計。
        df_feat_raw = add_features(df_raw, impute=False)
        train_raw, test_raw = time_split(df_feat_raw, test_days=test_days)
        imputer = fit_feature_imputer(train_raw)
        train = apply_feature_imputer(train_raw, imputer)
        test = apply_feature_imputer(test_raw, imputer)

        # Baseline
        self.baseline.fit(train)
        y_test = test["sales_qty"].to_numpy(dtype=float)
        ma_pred = self.baseline.predict_frame(test)
        ma_mae = mean_absolute_error(y_test, ma_pred)
        ma_mape = mape(y_test, ma_pred)

        # RandomForest
        X_train, y_train = prepare_xy(train)
        X_test, _ = prepare_xy(test)
        self.model.fit(X_train, y_train)
        rf_pred = self.model.predict(X_test)
        rf_mae = mean_absolute_error(y_test, rf_pred)
        rf_mape = mape(y_test, rf_pred)

        self.eval_results_ = [
            EvalResult("移動平均 (MA-7)", ma_mae, ma_mape, len(test)),
            EvalResult("RandomForest", rf_mae, rf_mape, len(test)),
        ]
        self.feature_importance_ = (
            pd.DataFrame(
                {"feature": self.feature_names_, "importance": self.model.feature_importances_}
            )
            .sort_values("importance", ascending=False)
            .reset_index(drop=True)
        )

        # 評估完成後以所有已知歷史重新 fit，供實際未來預測使用。
        df_feat_full = add_features(df_raw, impute=True)
        X_all, y_all = prepare_xy(df_feat_full)
        self.model.fit(X_all, y_all)
        self.baseline.fit(df_feat_full)
        self.history_df_ = df_feat_full.copy()
        self.trained_ = True
        return self.eval_results_

    def forecast(
        self,
        store_id: str,
        category_id: str,
        horizon: int = 7,
        future_promo_rate: float = 0.1,
    ) -> pd.DataFrame:
        """遞迴多步預測未來 horizon 日。"""
        if not self.trained_ or self.history_df_ is None:
            raise RuntimeError("模型尚未訓練")

        hist = self.history_df_[
            (self.history_df_["store_id"] == store_id)
            & (self.history_df_["category_id"] == category_id)
        ].sort_values("date")
        if hist.empty:
            raise ValueError("找不到該門市／品類資料")

        last = hist.iloc[-1]
        stable_seed = zlib.crc32(f"{store_id}|{category_id}".encode("utf-8"))
        rng = np.random.default_rng(stable_seed)
        cur = hist.copy()
        rows = []
        last_date = pd.Timestamp(last["date"])

        for step in range(1, horizon + 1):
            d = last_date + pd.Timedelta(days=step)
            dow = d.weekday()
            is_promo = int(rng.random() < future_promo_rate)
            base_price = float(hist["unit_price"].tail(14).mean())
            unit_price = base_price * (0.85 if is_promo else 1.0)
            is_holiday = int(dow >= 5)  # 簡化：週末視為高需求日

            new_row = {
                "date": d,
                "store_id": store_id,
                "store_name": last["store_name"],
                "region": last["region"],
                "category_id": category_id,
                "category_name": last["category_name"],
                "sales_qty": np.nan,
                "unit_price": unit_price,
                "is_promo": is_promo,
                "is_holiday": is_holiday,
                "day_of_week": dow,
                "inventory_end": np.nan,
                "staff_hours": np.nan,
            }
            tmp = pd.concat([cur, pd.DataFrame([new_row])], ignore_index=True)
            tmp = add_features(tmp)
            feat_row = tmp.iloc[[-1]][FEATURE_COLS].astype(float)
            pred = max(0.0, float(self.model.predict(feat_row)[0]))

            ma_hist = cur["sales_qty"].dropna().tolist()
            ma_pred = float(np.mean(ma_hist[-7:])) if ma_hist else 0.0

            rows.append(
                {
                    "date": d,
                    "store_id": store_id,
                    "category_id": category_id,
                    "pred_rf": round(pred, 1),
                    "pred_ma": round(ma_pred, 1),
                    "is_promo_assumed": is_promo,
                    "unit_price_assumed": round(unit_price, 1),
                    "day_of_week": dow,
                }
            )
            tmp.loc[tmp.index[-1], "sales_qty"] = pred
            cur = tmp

        return pd.DataFrame(rows)

    def save(self, path: Path | None = None) -> Path:
        p = path or CACHE_PATH
        bundle = {
            "model": self.model,
            "baseline_window": self.baseline.window,
            "baseline_last": self.baseline.last_values_,
            "feature_names": self.feature_names_,
            "eval_results": self.eval_results_,
            "feature_importance": self.feature_importance_,
            "history_df": self.history_df_,
            "trained": self.trained_,
        }
        joblib.dump(bundle, p)
        return p

    @classmethod
    def load(cls, path: Path | None = None) -> "DemandForecaster | None":
        p = path or CACHE_PATH
        if not p.exists():
            return None
        bundle = joblib.load(p)
        obj = cls()
        obj.model = bundle["model"]
        obj.baseline = MovingAverageBaseline(window=bundle.get("baseline_window", 7))
        obj.baseline.last_values_ = bundle.get("baseline_last", {})
        obj.feature_names_ = bundle["feature_names"]
        obj.eval_results_ = bundle["eval_results"]
        obj.feature_importance_ = bundle["feature_importance"]
        obj.history_df_ = bundle["history_df"]
        obj.trained_ = bundle["trained"]
        return obj


def get_or_train(df_raw: pd.DataFrame, force_retrain: bool = False) -> DemandForecaster:
    """載入快取或重新訓練。"""
    if not force_retrain:
        cached = DemandForecaster.load()
        if cached is not None and cached.trained_:
            return cached
    fc = DemandForecaster()
    fc.fit_eval(df_raw, test_days=60)
    fc.save()
    return fc


def eval_to_frame(results: list[EvalResult]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "模型": r.model_name,
                "MAE": round(r.mae, 2),
                "MAPE (%)": round(r.mape, 2),
                "測試樣本數": r.n_test,
            }
            for r in results
        ]
    )
