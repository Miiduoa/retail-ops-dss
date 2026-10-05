# -*- coding: utf-8 -*-
"""存取控制相關 UI：登入、再驗證、風險提示、作業／稽核／設定頁。"""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from .access.control import ControlPlane, DEMO_ACCOUNTS, risk_flag_label
from .access.policy import (
    ACTION_CATALOG,
    ROLE_LABELS,
    ROLE_PERMISSIONS,
    SCOPE_ALL,
    TZ_TAIPEI,
    AuthzDecision,
    Principal,
    PolicySettings,
    assess_access_risk,
)


def current_principal(cp: ControlPlane) -> Principal | None:
    uid = st.session_state.get("user_id")
    if not uid:
        return None
    sid = st.session_state.setdefault("session_id", "sess-pending")
    return cp.load_principal(
        uid,
        session_id=sid,
        last_stepup_at=st.session_state.get("last_stepup_at"),
    )


def _init_session() -> None:
    if "session_id" not in st.session_state:
        import uuid

        st.session_state.session_id = str(uuid.uuid4())
    st.session_state.setdefault("simulate_after_hours", False)


def render_login(cp: ControlPlane) -> Principal | None:
    _init_session()
    st.sidebar.subheader("登入（合成 Demo 帳號）")
    demo_labels = {
        a["username"]: f"{a['username']}｜{ROLE_LABELS.get(a['role'], a['role'])}"
        for a in DEMO_ACCOUNTS
    }
    pick = st.sidebar.selectbox(
        "快速填入帳號",
        options=list(demo_labels.keys()),
        format_func=lambda u: demo_labels[u],
        index=1,
    )
    picked = next(a for a in DEMO_ACCOUNTS if a["username"] == pick)
    username = st.sidebar.text_input("帳號", value=picked["username"])
    password = st.sidebar.text_input(
        "密碼",
        type="password",
        value=picked["password"],
        key=f"login_pw_{picked['username']}",
        help="合成 Demo 密碼已預填，非正式憑證。",
    )
    st.sidebar.caption("密碼見 README「Demo 帳號」；僅供作品展示，非正式憑證。")
    if st.sidebar.button("登入", type="primary"):
        principal, err = cp.authenticate(
            username,
            password,
            session_id=st.session_state.session_id,
            correlation_id=st.session_state.session_id,
        )
        if err:
            st.sidebar.error(err + "（已寫入稽核）")
        else:
            st.session_state.user_id = principal.user_id
            st.session_state.last_stepup_at = None
            st.rerun()
    return None


def render_identity(cp: ControlPlane, principal: Principal) -> None:
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"**{principal.display_name}**")
    st.sidebar.caption(
        f"{principal.username} · {principal.role_label} · 主店 {principal.home_store_id or '—'}"
    )
    if principal.sees_all_stores:
        st.sidebar.caption("資料範圍：全門市（全部）")
    else:
        st.sidebar.caption("資料範圍：" + "、".join(sorted(principal.store_scope)))
    stepup_ok = principal.stepup_is_fresh(
        datetime.now(TZ_TAIPEI),
        timedelta(minutes=cp.load_settings().stepup_minutes),
    )
    st.sidebar.caption(
        "工作階段信任：已再驗證" if stepup_ok else "工作階段信任：標準"
    )
    if not stepup_ok:
        st.sidebar.caption("敏感操作需再驗證")
    st.session_state.simulate_after_hours = st.sidebar.checkbox(
        "Demo：模擬非營業時間",
        value=st.session_state.get("simulate_after_hours", False),
        help="只為面試可重現「非營業時間」風險旗標，實際時鐘仍寫入稽核。",
    )
    if st.sidebar.button("登出"):
        cp.record_logout(principal, principal.session_id)
        for k in ("user_id", "last_stepup_at"):
            st.session_state.pop(k, None)
        st.rerun()


def render_risk_box(risk, title: str = "存取風險（若此刻送出）") -> None:
    mark = {"low": "低", "medium": "中", "high": "高"}[risk.level]
    icon = {"low": "🟢", "medium": "🟠", "high": "🔴"}[risk.level]
    st.markdown(f"**{title}：** {icon} {mark}")
    if risk.flags:
        st.caption(
            "旗標："
            + "、".join(f"{risk_flag_label(f)}（`{f}`）" for f in risk.flags)
        )
    for msg in risk.messages:
        if risk.level == "high":
            st.error(msg)
        elif risk.level == "medium":
            st.warning(msg)
        else:
            st.info(msg)
    if not risk.messages:
        st.caption("目前沒有額外營運風險旗標（仍須通過權限與門市範圍）。")


def render_decision_feedback(decision: AuthzDecision) -> None:
    meta = (
        f"outcome=`{decision.outcome}` · request_id=`{decision.request_id}` · "
        f"風險={decision.risk.level}"
    )
    if decision.allowed:
        st.success(decision.reason)
        st.caption(meta)
        return
    if decision.outcome == "challenge":
        st.warning(decision.reason)
        st.caption(meta)
        return
    st.error(decision.reason)
    st.caption(meta)


def render_stepup_form(cp: ControlPlane, principal: Principal, key: str) -> None:
    st.markdown("##### 提升工作階段信任等級")
    st.caption("敏感操作採「近期再驗證」，不是只靠登入角色。再驗證失敗也會寫入稽核。")
    pw = st.text_input("再輸入密碼", type="password", key=f"stepup_pw_{key}")
    if st.button("再驗證", key=f"stepup_btn_{key}"):
        if cp.verify_stepup(principal, pw, principal.session_id):
            st.session_state.last_stepup_at = datetime.now(TZ_TAIPEI)
            st.success("再驗證成功。請再執行一次原本的操作。")
            st.rerun()
        else:
            st.error("再驗證失敗，已記入稽核。")


def preview_action_risk(
    principal: Principal,
    action: str,
    store_id: str | None,
    quantity: float | None,
    settings: PolicySettings,
    simulate_after_hours: bool,
):
    return assess_access_risk(
        action=action,
        principal=principal,
        store_id=store_id,
        quantity=quantity,
        now=datetime.now(TZ_TAIPEI),
        settings=settings,
        simulate_after_hours=simulate_after_hours,
    )


def page_ops(
    df: pd.DataFrame,
    cp: ControlPlane,
    principal: Principal,
    store_meta: pd.DataFrame,
    cat_meta: pd.DataFrame,
) -> None:
    st.header("📦 庫存調整與補貨核准")
    st.markdown(
        "敏感作業走 **資源＋動作** 授權（`inventory.write`、`reorder.approve`），"
        "並套用門市資料範圍。通過後才寫入營運資料；拒絕／待再驗證同樣進稽核。"
    )
    allowed = principal.allowed_store_ids(store_meta["store_id"].tolist())
    if not allowed:
        st.error("你的帳號沒有任何門市範圍。")
        return
    name_of = store_meta.set_index("store_id")["store_name"].to_dict()
    cat_name = cat_meta.set_index("category_id")["category_name"].to_dict()
    sim = bool(st.session_state.get("simulate_after_hours"))

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("庫存調整")
        sid = st.selectbox(
            "門市",
            allowed,
            format_func=lambda s: f"{s} — {name_of.get(s, s)}",
            key="adj_store",
        )
        cid = st.selectbox(
            "品類",
            cat_meta["category_id"].tolist(),
            format_func=lambda c: f"{c} — {cat_name.get(c, c)}",
            key="adj_cat",
        )
        hist = df[(df["store_id"] == sid) & (df["category_id"] == cid)].sort_values("date")
        base = float(hist["inventory_end"].iloc[-1]) if len(hist) else 0.0
        effective = base + cp.inventory_delta(sid, cid)
        st.metric("目前有效庫存（CSV 末日＋調整）", f"{effective:.0f} 件")
        delta = st.number_input("調整量（可正可負）", value=10, step=1, key="adj_delta")
        reason = st.text_input("原因", value="盤點校正", key="adj_reason")
        risk = preview_action_risk(
            principal, "inventory.write", sid, float(delta), cp.load_settings(), sim
        )
        render_risk_box(risk, "庫存調整存取風險")
        write_label = (
            "送出庫存調整"
            if "inventory.write" in principal.permissions
            else "示範：嘗試調整庫存（預期被拒絕）"
        )
        if st.button(write_label, type="primary"):
            d = cp.adjust_inventory(
                principal,
                store_id=sid,
                category_id=cid,
                delta=int(delta),
                reason=reason,
                correlation_id=principal.session_id,
                simulate_after_hours=sim,
                base_inventory=effective,
            )
            render_decision_feedback(d)
            if d.outcome == "challenge":
                render_stepup_form(cp, principal, "inv")

        recent = cp.list_adjustments(allowed if not principal.sees_all_stores else None)
        if recent:
            st.caption("最近庫存調整")
            adj_df = pd.DataFrame(recent).head(15)
            adj_df = adj_df.rename(
                columns={
                    "adj_id": "編號",
                    "store_id": "門市",
                    "category_id": "品類",
                    "delta": "調整量",
                    "reason": "原因",
                    "actor_id": "操作者",
                    "request_id": "request_id",
                    "created_at": "時間",
                }
            )
            st.dataframe(adj_df, hide_index=True, use_container_width=True)

    with c2:
        st.subheader("補貨申請／核准")
        tickets = cp.list_tickets(None if principal.sees_all_stores else allowed)
        if tickets:
            show = pd.DataFrame(tickets).rename(
                columns={
                    "ticket_id": "單號",
                    "store_id": "門市",
                    "category_id": "品類",
                    "recommended_qty": "建議量",
                    "status": "狀態",
                    "risk_level": "風險",
                    "risk_flags": "旗標",
                    "created_by": "申請人",
                    "decided_by": "核准人",
                    "created_at": "建立時間",
                    "decided_at": "決行時間",
                    "request_id": "request_id",
                    "note": "備註",
                }
            )
            st.dataframe(show, hide_index=True, use_container_width=True)
            pending = [t for t in tickets if t["status"] == "pending"]
            if pending:
                tmap = {
                    t["ticket_id"]: (
                        f"{t['ticket_id']}｜{t['store_id']}/{t['category_id']}｜"
                        f"{t['recommended_qty']}件｜風險{t['risk_level']}"
                    )
                    for t in pending
                }
                pick = st.selectbox(
                    "待決補貨單",
                    list(tmap.keys()),
                    format_func=lambda k: tmap[k],
                )
                chosen = next(t for t in pending if t["ticket_id"] == pick)
                prisk = preview_action_risk(
                    principal,
                    "reorder.approve",
                    chosen["store_id"],
                    float(chosen["recommended_qty"]),
                    cp.load_settings(),
                    sim,
                )
                render_risk_box(prisk, "核准此單的存取風險")
                b1, b2 = st.columns(2)
                with b1:
                    if st.button("核准補貨"):
                        d = cp.decide_reorder(
                            principal,
                            ticket_id=pick,
                            approve=True,
                            correlation_id=principal.session_id,
                            simulate_after_hours=sim,
                        )
                        render_decision_feedback(d)
                        if d.outcome == "challenge":
                            render_stepup_form(cp, principal, "appr")
                with b2:
                    if st.button("駁回補貨"):
                        d = cp.decide_reorder(
                            principal,
                            ticket_id=pick,
                            approve=False,
                            correlation_id=principal.session_id,
                            simulate_after_hours=sim,
                        )
                        render_decision_feedback(d)
                        if d.outcome == "challenge":
                            render_stepup_form(cp, principal, "rej")
            else:
                st.info("目前沒有待決補貨單。請到「預測與決策建議」提出申請。")
        else:
            st.info("尚無補貨單。請先在預測頁提出申請。")


def page_audit(cp: ControlPlane, principal: Principal) -> None:
    st.header("🔎 操作稽核")
    gate = cp.authorize(
        principal,
        "audit.read",
        resource_type="audit",
        resource_id="log",
        correlation_id=principal.session_id,
        payload_summary="開啟稽核頁",
        audit_outcomes=("deny", "challenge"),
    )
    if not gate.allowed:
        render_decision_feedback(gate)
        return
    st.markdown(
        "追加寫入、不可改刪。欄位含 actor、action、resource、outcome、timestamp、"
        "request_id／correlation_id。管理者可看**失敗授權**與**敏感成功操作**。"
    )
    stats = cp.audit_stats(24)
    m = st.columns(4)
    m[0].metric("近 24h 拒絕", stats["deny_recent"])
    m[1].metric("近 24h 待再驗證", stats["challenge_recent"])
    m[2].metric("近 24h 敏感成功", stats["sensitive_allow_recent"])
    m[3].metric("近 24h 高風險事件", stats["high_risk_recent"])

    all_rows = cp.query_audit(limit=1000)
    actors = sorted({r["actor_username"] for r in all_rows if r.get("actor_username")})
    actions = sorted({r["action"] for r in all_rows if r.get("action")})
    stores = sorted({r["store_id"] for r in all_rows if r.get("store_id")})

    f1, f2, f3, f4 = st.columns(4)
    with f1:
        actor = st.selectbox("操作者", ["（全部）"] + actors)
    with f2:
        action = st.selectbox("動作", ["（全部）"] + actions)
    with f3:
        outcome = st.selectbox("結果", ["（全部）", "allow", "deny", "challenge"])
    with f4:
        store = st.selectbox("門市", ["（全部）"] + stores)
    req = st.text_input("request_id 或 correlation_id")
    rows = cp.query_audit(
        actor=None if actor.startswith("（") else actor,
        action=None if action.startswith("（") else action,
        outcome=None if outcome.startswith("（") else outcome,
        store_id=None if store.startswith("（") else store,
        request_id=req.strip() or None,
        limit=500,
    )
    table = pd.DataFrame(rows)
    if table.empty:
        st.info("沒有符合篩選的事件。")
        return
    show_cols = [
        c
        for c in [
            "timestamp",
            "actor_username",
            "actor_role",
            "action",
            "store_id",
            "resource_id",
            "outcome",
            "risk_level",
            "risk_flags",
            "payload_summary",
            "deny_reason",
            "request_id",
            "correlation_id",
        ]
        if c in table.columns
    ]
    st.dataframe(table[show_cols], hide_index=True, use_container_width=True, height=420)
    if "audit.export" in principal.permissions:
        csv_text = cp.export_audit_csv(rows)
        st.download_button(
            "匯出目前篩選結果（CSV）",
            data=csv_text.encode("utf-8-sig"),
            file_name="audit_export.csv",
            mime="text/csv",
        )
    else:
        st.caption("目前角色沒有 `audit.export`，無法下載。")


def page_admin(cp: ControlPlane, principal: Principal) -> None:
    st.header("⚙️ 帳號、範圍與設定")
    st.markdown(
        "`settings.admin`／`user.admin` 僅限**管理者工作階段**，並需要近期再驗證。"
        "角色權限與門市範圍分開：同一 `operator` 仍可能只能看到不同門市。"
    )
    settings = cp.load_settings()
    st.subheader("政策設定")
    col = st.columns(4)
    hi = col[0].number_input("高影響件數門檻", min_value=1, value=int(settings.high_impact_qty))
    bh1 = col[1].number_input("營業開始（時）", min_value=0, max_value=23, value=int(settings.business_hour_start))
    bh2 = col[2].number_input("營業結束（時）", min_value=1, max_value=24, value=int(settings.business_hour_end))
    sm = col[3].number_input("再驗證有效分鐘", min_value=1, max_value=60, value=int(settings.stepup_minutes))
    if st.button("儲存政策設定"):
        last = None
        for key, val in [
            ("high_impact_qty", str(int(hi))),
            ("business_hour_start", str(int(bh1))),
            ("business_hour_end", str(int(bh2))),
            ("stepup_minutes", str(int(sm))),
        ]:
            last = cp.update_setting(principal, key, val, correlation_id=principal.session_id)
            if not last.allowed:
                break
        if last is not None:
            render_decision_feedback(last)
            if last.outcome == "challenge":
                render_stepup_form(cp, principal, "settings")

    st.subheader("帳號與門市範圍")
    users = cp.list_users()
    view = pd.DataFrame(
        [
            {
                "帳號": u["username"],
                "姓名": u["display_name"],
                "角色": ROLE_LABELS.get(u["role"], u["role"]),
                "主店": u["home_store_id"],
                "範圍": ",".join(u["stores"]),
                "啟用": bool(u["is_active"]),
            }
            for u in users
        ]
    )
    st.dataframe(view, hide_index=True, use_container_width=True)

    umap = {u["user_id"]: f"{u['username']}（{u['display_name']}）" for u in users}
    tid = st.selectbox("選擇帳號", list(umap.keys()), format_func=lambda k: umap[k])
    target = next(u for u in users if u["user_id"] == tid)
    role = st.selectbox(
        "角色",
        list(ROLE_PERMISSIONS.keys()),
        index=list(ROLE_PERMISSIONS.keys()).index(target["role"]),
        format_func=lambda r: ROLE_LABELS.get(r, r),
    )
    store_opts = ["S01", "S02", "S03", "S04", SCOPE_ALL]
    current = target["stores"]
    stores = st.multiselect(
        "門市範圍（`*` 代表全門市）",
        store_opts,
        default=[s for s in current if s in store_opts] or current,
    )
    active = st.checkbox("帳號啟用", value=bool(target["is_active"]))
    if st.button("儲存帳號變更"):
        d = cp.update_user(
            principal,
            target_user_id=tid,
            role=role,
            stores=stores or ["S01"],
            is_active=active,
            correlation_id=principal.session_id,
        )
        render_decision_feedback(d)
        if d.outcome == "challenge":
            render_stepup_form(cp, principal, "user")

    st.subheader("角色 → 權限對照（預設拒絕未列項目）")
    rows = []
    for role_id, perms in ROLE_PERMISSIONS.items():
        for p in sorted(perms):
            rows.append(
                {
                    "角色": ROLE_LABELS[role_id],
                    "權限": p,
                    "說明": ACTION_CATALOG.get(p, ""),
                }
            )
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True, height=280)


def nav_pages(principal: Principal) -> list[str]:
    pages = []
    if "dashboard.read" in principal.permissions:
        pages.append("資料概覽")
    if "forecast.read" in principal.permissions:
        pages.append("預測與決策建議")
    if {"inventory.read", "inventory.write", "reorder.read", "reorder.approve"} & principal.permissions:
        pages.append("庫存與補貨作業")
    if "eval.read" in principal.permissions:
        pages.append("模型評估對照")
    if "audit.read" in principal.permissions:
        pages.append("操作稽核")
    if {"settings.admin", "user.admin"} & principal.permissions:
        pages.append("帳號與設定")
    return pages or ["資料概覽"]
