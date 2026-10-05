# -*- coding: utf-8 -*-
"""
零售營運決策支援原型（DSS）
Streamlit 入口：預測、可解釋性、補貨／人力建議、模型評估，以及應用層授權／稽核。
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

from src.access.control import get_control_plane
from src.data_loader import list_categories, list_stores, load_sales
from src.explain import labelize, similar_history_days, top_feature_importance
from src.models import eval_to_frame, get_or_train
from src.recommend import combined_advice, replenishment_need
from src.ui_security import (
    current_principal,
    nav_pages,
    page_admin,
    page_audit,
    page_ops,
    preview_action_risk,
    render_decision_feedback,
    render_identity,
    render_login,
    render_risk_box,
    render_stepup_form,
)

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


def _effective_inventory(df: pd.DataFrame, cp, store_id: str, category_id: str) -> float:
    hist = df[(df["store_id"] == store_id) & (df["category_id"] == category_id)].sort_values("date")
    base = float(hist["inventory_end"].iloc[-1]) if len(hist) else 0.0
    return base + cp.inventory_delta(store_id, category_id)


def page_forecast(df: pd.DataFrame, fc, cp, principal):
    st.header("📈 需求預測與決策建議")
    stores = list_stores(df)
    cats = list_categories(df)
    allowed = principal.allowed_store_ids(stores["store_id"].tolist())
    if not allowed:
        st.error("沒有可檢視的門市範圍。")
        return

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        store_label = st.selectbox(
            "門市",
            options=allowed,
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

    # 讀取預測仍走授權（指定門市資源）；被拒則不展示他店數字
    read = cp.authorize(
        principal,
        "forecast.read",
        resource_type="store_category",
        resource_id=f"{store_label}:{cat_label}",
        store_id=store_label,
        correlation_id=principal.session_id,
        payload_summary=f"檢視預測 {store_label}/{cat_label}",
        audit_outcomes=("deny", "challenge"),
    )
    if not read.allowed:
        render_decision_feedback(read)
        return

    hist = df[(df["store_id"] == store_label) & (df["category_id"] == cat_label)].sort_values(
        "date"
    )
    recent_inv = _effective_inventory(df, cp, store_label, cat_label)

    forecast = fc.forecast(store_label, cat_label, horizon=horizon, future_promo_rate=promo_rate)

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
    m3.metric("有效庫存（含調整）", f"{recent_inv:.0f} 件")

    st.subheader("決策建議（規則型 DSS）")
    st.markdown(combined_advice(forecast, recent_inv))

    need, gap = replenishment_need(forecast, recent_inv)
    suggest_qty = max(0, int(round(gap))) if gap > 0 else 0
    st.markdown(f"**建議補貨量（缺口）：** {suggest_qty} 件（備貨需求約 {need:.0f} 件）")
    submit_qty = st.number_input(
        "本次送出／核准數量",
        min_value=1,
        value=max(suggest_qty, 1),
        step=10,
        help="可調高超過高影響門檻（預設 300）以演示再驗證。",
    )

    sim = bool(st.session_state.get("simulate_after_hours"))
    settings = cp.load_settings()
    risk = preview_action_risk(
        principal,
        "reorder.approve",
        store_label,
        float(submit_qty),
        settings,
        sim,
    )
    render_risk_box(risk, "補貨核准存取風險")
    st.caption("風險規則可解釋：高影響數量、非營業時間、跨店（相對主店）。送出後才寫入稽核。")

    b1, b2, b3 = st.columns(3)
    with b1:
        if st.button("提出補貨申請", type="primary"):
            d, tid = cp.create_reorder(
                principal,
                store_id=store_label,
                category_id=cat_label,
                qty=int(submit_qty),
                correlation_id=principal.session_id,
                simulate_after_hours=sim,
                note="由預測頁 DSS 建議產生",
            )
            render_decision_feedback(d)
            if tid:
                st.info(f"已建立補貨單 `{tid}`，請到「庫存與補貨作業」核准。")
            if d.outcome == "challenge":
                render_stepup_form(cp, principal, "req")
    with b2:
        if st.button("直接核准此補貨"):
            d, tid = cp.create_reorder(
                principal,
                store_id=store_label,
                category_id=cat_label,
                qty=int(submit_qty),
                correlation_id=principal.session_id,
                simulate_after_hours=sim,
                note="預測頁直接核准前之申請",
            )
            if not d.allowed:
                render_decision_feedback(d)
                if d.outcome == "challenge":
                    render_stepup_form(cp, principal, "dirreq")
            else:
                ad = cp.decide_reorder(
                    principal,
                    ticket_id=tid,
                    approve=True,
                    correlation_id=principal.session_id,
                    simulate_after_hours=sim,
                )
                render_decision_feedback(ad)
                if ad.outcome == "challenge":
                    render_stepup_form(cp, principal, "dirappr")
    with b3:
        if "reorder.approve" not in principal.permissions:
            if st.button("示範：嘗試核准（預期被拒絕）"):
                d = cp.authorize(
                    principal,
                    "reorder.approve",
                    resource_type="store_category",
                    resource_id=f"{store_label}:{cat_label}",
                    store_id=store_label,
                    quantity=float(submit_qty),
                    correlation_id=principal.session_id,
                    simulate_after_hours=sim,
                    payload_summary="檢視者示範嘗試核准補貨",
                )
                render_decision_feedback(d)

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
        sim_hist = similar_history_days(
            fc.history_df_[
                (fc.history_df_["store_id"] == store_label)
                & (fc.history_df_["category_id"] == cat_label)
            ],
            target_dow=target_dow,
            is_promo=target_promo,
            top_n=5,
        )
        if not sim_hist.empty:
            sim_show = sim_hist.copy()
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


def page_eval(fc, cp, principal):
    st.header("🧪 模型評估對照")
    gate = cp.authorize(
        principal,
        "eval.read",
        resource_type="model",
        resource_id="holdout",
        correlation_id=principal.session_id,
        payload_summary="檢視模型評估",
        audit_outcomes=("deny", "challenge"),
    )
    if not gate.allowed:
        render_decision_feedback(gate)
        return
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


def page_overview(df: pd.DataFrame, principal):
    st.header("🏪 資料與系統概覽")
    st.markdown(
        """
本原型模擬連鎖零售的**日銷量預測 → 可解釋儀表板 → 補貨／人力決策建議**流程，
並以應用層 **細粒度授權、門市資料範圍、操作稽核** 把建議關進可課責的作業閉環。
數字已依你的門市範圍過濾。
"""
    )
    if principal.sees_all_stores:
        st.caption("目前資料範圍：全門市。")
    else:
        st.caption("目前資料範圍：" + "、".join(sorted(principal.store_scope)))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("資料列數", f"{len(df):,}")
    c2.metric("門市數", df["store_id"].nunique())
    c3.metric("品類數", df["category_id"].nunique())
    c4.metric("日期範圍", f"{df['date'].min().date()} ~ {df['date'].max().date()}")

    daily = df.groupby("date", as_index=False)["sales_qty"].sum()
    fig = px.line(daily, x="date", y="sales_qty", title="可見範圍之日銷量總和")
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
    cp = get_control_plane()
    st.sidebar.title("營運 DSS 原型")
    st.sidebar.caption("預測＋可解釋儀表板 · 應用層授權／稽核")

    principal = current_principal(cp)
    if principal is None:
        render_login(cp)
        st.header("請先登入後再使用 DSS")
        st.markdown(
            """
本畫面在登入前**不會載入他店營運數字**。請用 README 的合成 Demo 帳號：

| 帳號 | 角色 | 可見門市 |
|------|------|----------|
| `operator.s01` | 門市營運 | 僅 S01 台北信義店 |
| `operator.north` | 門市營運 | S01、S04（北區） |
| `operator.s03` | 門市營運 | 僅 S03 高雄夢時代店 |
| `viewer.s02` | 檢視者 | 僅 S02；無寫入／核准 |
| `admin` | 系統管理者 | 全門市；稽核與設定 |

側欄可快速填入帳號，密碼見 README。登入失敗會寫入稽核。
"""
        )
        st.caption("台灣資管碩士備審專題原型 · 僅供學術 Demo，非生產環境系統。")
        return

    render_identity(cp, principal)
    pages = nav_pages(principal)
    page = st.sidebar.radio("頁面", pages, index=min(1, len(pages) - 1) if "預測與決策建議" in pages else 0)

    df_all = _load_df()
    df = cp.scoped_sales(df_all, principal)

    needs_model = page in {"預測與決策建議", "模型評估對照"}
    fc = None
    if needs_model:
        if "model.retrain" in principal.permissions:
            force = st.sidebar.button("重新訓練模型")
            if force:
                d = cp.authorize(
                    principal,
                    "model.retrain",
                    resource_type="model",
                    resource_id="rf_bundle",
                    correlation_id=principal.session_id,
                    payload_summary="重新訓練預測模型",
                )
                if d.allowed:
                    st.cache_resource.clear()
                    fc = _get_forecaster(force=True)
                    st.sidebar.success("已重新訓練並快取")
                else:
                    st.sidebar.error(d.reason)
                    if d.outcome == "challenge":
                        render_stepup_form(cp, principal, "retrain")
                    fc = _get_forecaster(force=False)
            else:
                fc = _get_forecaster(force=False)
        else:
            fc = _get_forecaster(force=False)

    st.sidebar.markdown("---")
    st.sidebar.markdown("**備審 Demo 提示**")
    st.sidebar.markdown(
        "1. 用 `operator.s01` 看只能選信義店\n"
        "2. 提出／核准補貨，看存取風險\n"
        "3. 勾選模擬非營業時間再操作\n"
        "4. 換 `admin` 看稽核拒絕與敏感成功\n"
        "5. `viewer.s02` 嘗試核准應被拒絕"
    )

    stores = list_stores(df_all)
    cats = list_categories(df_all)

    if page == "資料概覽":
        ov = cp.authorize(
            principal,
            "dashboard.read",
            resource_type="dashboard",
            resource_id="overview",
            store_id=principal.home_store_id,
            correlation_id=principal.session_id,
            payload_summary="開啟資料概覽",
            audit_outcomes=("deny", "challenge"),
        )
        if ov.allowed:
            page_overview(df, principal)
        else:
            render_decision_feedback(ov)
    elif page == "預測與決策建議":
        page_forecast(df, fc, cp, principal)
    elif page == "庫存與補貨作業":
        page_ops(df, cp, principal, stores, cats)
    elif page == "模型評估對照":
        page_eval(fc, cp, principal)
    elif page == "操作稽核":
        page_audit(cp, principal)
    elif page == "帳號與設定":
        page_admin(cp, principal)

    st.markdown("---")
    st.caption("台灣資管碩士備審專題原型 · 僅供學術 Demo，非生產環境系統。")


if __name__ == "__main__":
    main()
