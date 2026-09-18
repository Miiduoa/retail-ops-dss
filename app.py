# -*- coding: utf-8 -*-
"""
零售營運決策支援原型（DSS）
Streamlit 入口：預測、可解釋性、補貨／人力建議、模型評估對照。
執行：streamlit run app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data_loader import list_categories, list_stores, load_sales
from src.explain import labelize, similar_history_days, top_feature_importance
from src.models import eval_to_frame, get_or_train
from src.recommend import combined_advice

st.set_page_config(
    page_title="零售營運決策支援原型",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data(show_spinner=False)
def _load_df():
    return load_sales()


@st.cache_resource(show_spinner="首次載入：訓練模型並快取中…")
def _get_forecaster(force: bool = False):
    df = _load_df()
    return get_or_train(df, force_retrain=force)


def page_forecast(df: pd.DataFrame, fc):
    st.header("📈 需求預測與決策建議")
    stores = list_stores(df)
    cats = list_categories(df)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        store_label = st.selectbox(
            "門市",
            options=stores["store_id"].tolist(),
            format_func=lambda sid: f"{sid} — {stores.set_index('store_id').loc[sid, 'store_name']}",
        )
    with c2:
        cat_label = st.selectbox(
            "品類",
            options=cats["category_id"].tolist(),
            format_func=lambda cid: f"{cid} — {cats.set_index('category_id').loc[cid, 'category_name']}",
        )
    with c3:
        horizon = st.slider("預測天數 N", min_value=3, max_value=14, value=7)
    with c4:
        promo_rate = st.slider("未來促銷機率（假設）", 0.0, 0.4, 0.1, 0.05)

    hist = df[(df["store_id"] == store_label) & (df["category_id"] == cat_label)].sort_values(
        "date"
    )
    recent_inv = float(hist["inventory_end"].tail(7).mean()) if len(hist) else 0.0

    forecast = fc.forecast(store_label, cat_label, horizon=horizon, future_promo_rate=promo_rate)

    # 歷史 + 預測圖
    hist_tail = hist.tail(60)
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=hist_tail["date"],
            y=hist_tail["sales_qty"],
            name="歷史銷量",
            mode="lines",
            line=dict(color="#1f77b4"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=forecast["date"],
            y=forecast["pred_rf"],
            name="RF 預測",
            mode="lines+markers",
            line=dict(color="#ff7f0e", dash="dash"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=forecast["date"],
            y=forecast["pred_ma"],
            name="MA-7 對照",
            mode="lines+markers",
            line=dict(color="#2ca02c", dash="dot"),
        )
    )
    fig.update_layout(
        title="歷史銷量與未來 N 日預測",
        xaxis_title="日期",
        yaxis_title="銷量（件）",
        height=420,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(l=40, r=20, t=60, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)

    m1, m2, m3 = st.columns(3)
    m1.metric("預測日均", f"{forecast['pred_rf'].mean():.0f} 件")
    m2.metric("預測尖峰", f"{forecast['pred_rf'].max():.0f} 件")
    m3.metric("近7日庫存均值", f"{recent_inv:.0f} 件")

    st.subheader("決策建議（規則型 DSS）")
    st.markdown(combined_advice(forecast, recent_inv))

    with st.expander("查看預測明細表"):
        show = forecast.copy()
        show["date"] = show["date"].dt.strftime("%Y-%m-%d")
        show = show.rename(
            columns={
                "date": "日期",
                "pred_rf": "RF預測",
                "pred_ma": "MA預測",
                "is_promo_assumed": "假設促銷",
                "unit_price_assumed": "假設單價",
                "day_of_week": "星期",
            }
        )
        st.dataframe(show.drop(columns=["store_id", "category_id"], errors="ignore"), hide_index=True)

    st.subheader("可解釋性")
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**特徵重要性（RandomForest）**")
        imp = labelize(top_feature_importance(fc.feature_importance_, 8))
        fig_imp = px.bar(
            imp,
            x="重要性",
            y="特徵",
            orientation="h",
            title="驅動預測的主要特徵",
        )
        fig_imp.update_layout(yaxis={"categoryorder": "total ascending"}, height=360)
        st.plotly_chart(fig_imp, use_container_width=True)
        st.caption("重要性愈高，表示該特徵對模型分割／預測的貢獻愈大（全域解釋）。")

    with col_b:
        st.markdown("**類似歷史日對照**")
        target_dow = int(forecast.iloc[0]["day_of_week"])
        target_promo = int(forecast.iloc[0]["is_promo_assumed"])
        sim = similar_history_days(
            fc.history_df_[
                (fc.history_df_["store_id"] == store_label)
                & (fc.history_df_["category_id"] == cat_label)
            ],
            target_dow=target_dow,
            is_promo=target_promo,
            top_n=5,
        )
        if not sim.empty:
            sim_show = sim.copy()
            sim_show["date"] = pd.to_datetime(sim_show["date"]).dt.strftime("%Y-%m-%d")
            sim_show = sim_show.rename(
                columns={
                    "date": "日期",
                    "sales_qty": "銷量",
                    "is_promo": "促銷",
                    "is_holiday": "假日",
                    "unit_price": "單價",
                    "day_of_week": "星期",
                }
            )
            st.dataframe(sim_show, hide_index=True)
            st.caption(
                f"對照條件：與預測首日相近（星期={target_dow}、促銷≈{target_promo}）的歷史實績，"
                "協助管理者用「過去類似日子」理解預測合理性。"
            )
        else:
            st.info("無足夠歷史可對照。")


def page_eval(fc):
    st.header("🧪 模型評估對照")
    st.markdown(
        "以**時間切分**（最後 60 日為測試集）評估，避免隨機切分造成的未來資訊洩漏。"
    )
    table = eval_to_frame(fc.eval_results_)
    st.dataframe(table, hide_index=True, use_container_width=True)

    fig = go.Figure(
        data=[
            go.Bar(name="MAE", x=table["模型"], y=table["MAE"]),
            go.Bar(name="MAPE (%)", x=table["模型"], y=table["MAPE (%)"]),
        ]
    )
    fig.update_layout(
        barmode="group",
        title="Baseline vs 進階模型",
        height=400,
    )
    st.plotly_chart(fig, use_container_width=True)

    best = min(fc.eval_results_, key=lambda r: r.mae)
    st.success(
        f"測試集 MAE 最低者：**{best.model_name}**（MAE={best.mae:.2f}，MAPE={best.mape:.2f}%）。"
        " 進階模型若優於移動平均，代表滯後／促銷／價格等特徵有額外解釋力。"
    )
    st.markdown(
        """
**指標說明**
- **MAE**：平均絕對誤差（件），愈低愈好，單位直觀。
- **MAPE**：平均絕對百分比誤差（%），便於跨品類比較；實際銷量為 0 的樣本已排除。
"""
    )


def page_overview(df: pd.DataFrame):
    st.header("🏪 資料與系統概覽")
    st.markdown(
        """
本原型模擬連鎖零售的**日銷量預測 → 可解釋儀表板 → 補貨／人力決策建議**流程，
對應資管研究所強調的「AI／資料驅動資訊系統與決策支援」。
"""
    )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("資料列數", f"{len(df):,}")
    c2.metric("門市數", df["store_id"].nunique())
    c3.metric("品類數", df["category_id"].nunique())
    c4.metric("日期範圍", f"{df['date'].min().date()} ~ {df['date'].max().date()}")

    daily = df.groupby("date", as_index=False)["sales_qty"].sum()
    fig = px.line(daily, x="date", y="sales_qty", title="全通路日銷量總和")
    fig.update_layout(height=360)
    st.plotly_chart(fig, use_container_width=True)

    by_cat = (
        df.groupby("category_name", as_index=False)["sales_qty"]
        .mean()
        .sort_values("sales_qty", ascending=False)
    )
    fig2 = px.bar(by_cat, x="category_name", y="sales_qty", title="品類平均日銷量")
    fig2.update_layout(height=320)
    st.plotly_chart(fig2, use_container_width=True)

    with st.expander("資料欄位說明"):
        st.markdown(
            """
| 欄位 | 說明 |
|------|------|
| date | 營業日 |
| store_id / store_name / region | 門市與區域 |
| category_id / category_name | 品類 |
| sales_qty | 當日銷量（件） |
| unit_price | 當日均價 |
| is_promo / is_holiday | 促銷、假日標記 |
| inventory_end / staff_hours | 庫存與工時（決策建議用） |
"""
        )
    st.info("資料為可重現合成零售日銷量（`python generate_data.py`），固定隨機種子 SEED=42。")


def main():
    st.sidebar.title("營運 DSS 原型")
    st.sidebar.caption("構想 A｜預測＋可解釋儀表板")
    page = st.sidebar.radio(
        "頁面",
        ["資料概覽", "預測與決策建議", "模型評估對照"],
        index=1,
    )
    force = st.sidebar.button("重新訓練模型")
    df = _load_df()
    if force:
        st.cache_resource.clear()
        fc = _get_forecaster(force=True)
        st.sidebar.success("已重新訓練並快取")
    else:
        fc = _get_forecaster(force=False)

    st.sidebar.markdown("---")
    st.sidebar.markdown("**備審 Demo 提示**")
    st.sidebar.markdown(
        "1. 選門市／品類 → 調 N 日\n"
        "2. 說明 RF vs MA\n"
        "3. 指特徵重要性與類似歷史\n"
        "4. 讀出補貨／人力建議"
    )

    if page == "資料概覽":
        page_overview(df)
    elif page == "預測與決策建議":
        page_forecast(df, fc)
    else:
        page_eval(fc)

    st.markdown("---")
    st.caption("台灣資管碩士備審專題原型 · 僅供學術 Demo，非生產環境系統。")


if __name__ == "__main__":
    main()
