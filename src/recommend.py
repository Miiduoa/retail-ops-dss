# -*- coding: utf-8 -*-
"""依預測結果產生補貨／人力文字建議（規則型決策支援）。"""

from __future__ import annotations

import pandas as pd


def replenishment_need(
    forecast: pd.DataFrame,
    recent_inventory: float,
    lead_time_days: int = 2,
    service_buffer: float = 0.20,
) -> tuple[float, float]:
    """回傳 (建議備貨量 need, 缺口 gap)。gap>0 表示應補貨。"""
    need = float(forecast["pred_rf"].head(lead_time_days + 3).sum()) * (1 + service_buffer)
    gap = need - float(recent_inventory)
    return need, gap


def replenishment_advice(
    forecast: pd.DataFrame,
    recent_inventory: float,
    lead_time_days: int = 2,
    service_buffer: float = 0.20,
) -> str:
    """補貨建議：涵蓋 lead_time + 緩衝。"""
    need, gap = replenishment_need(
        forecast, recent_inventory, lead_time_days, service_buffer
    )
    avg_daily = float(forecast["pred_rf"].mean())
    peak = float(forecast["pred_rf"].max())
    peak_day = str(forecast.loc[forecast["pred_rf"].idxmax(), "date"])[:10]

    lines = [
        "【補貨建議】",
        f"• 未來 {len(forecast)} 日預測日均需求約 {avg_daily:.0f} 件，尖峰 {peak:.0f} 件（{peak_day}）。",
        f"• 考量前置期 {lead_time_days} 日 + {int(service_buffer*100)}% 服務水準緩衝，建議備貨量約 {need:.0f} 件。",
    ]
    if gap > 0:
        lines.append(f"• 目前估列庫存約 {recent_inventory:.0f} 件，缺口約 {gap:.0f} 件 → **建議立即下單補貨**。")
    elif gap > -need * 0.15:
        lines.append(f"• 目前估列庫存約 {recent_inventory:.0f} 件，大致足夠 → **維持觀察，可小量補貨**。")
    else:
        lines.append(f"• 目前估列庫存約 {recent_inventory:.0f} 件，高於需求 → **暫緩進貨，優先去化庫存**。")
    return "\n".join(lines)


def staffing_advice(forecast: pd.DataFrame, productivity: float = 40.0) -> str:
    """人力建議：以預測量／產能粗估工時。"""
    # productivity：每人每小時可處理件數（示意）
    daily = forecast[["date", "pred_rf", "day_of_week"]].copy()
    daily["est_hours"] = (daily["pred_rf"] / productivity).clip(lower=3)
    weekend = daily[daily["day_of_week"] >= 5]
    weekday = daily[daily["day_of_week"] < 5]

    lines = [
        "【人力配置建議】",
        f"• 預測區間平日平均約需 {weekday['est_hours'].mean():.1f} 工時／日；"
        f"週末約 {weekend['est_hours'].mean():.1f} 工時／日（產能假設 {productivity:.0f} 件／人時）。",
    ]
    if not weekend.empty and weekend["est_hours"].mean() > weekday["est_hours"].mean() * 1.15:
        lines.append("• 週末需求明顯偏高 → **建議加開 1 班或調派支援人力**。")
    else:
        lines.append("• 週末與平日差距有限 → **維持既有班表，尖峰日彈性加班即可**。")

    top = daily.sort_values("est_hours", ascending=False).head(2)
    peak_txt = "、".join(
        f"{str(r.date)[:10]}（約 {r.est_hours:.1f}h）" for r in top.itertuples()
    )
    lines.append(f"• 需特別留意的日期：{peak_txt}。")
    return "\n".join(lines)


def combined_advice(
    forecast: pd.DataFrame,
    recent_inventory: float,
) -> str:
    return (
        replenishment_advice(forecast, recent_inventory)
        + "\n\n"
        + staffing_advice(forecast)
    )
