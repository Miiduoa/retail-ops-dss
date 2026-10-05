# -*- coding: utf-8 -*-
"""控制平面：種子帳號、登入、授權＋稽核、庫存／補貨、設定與帳號管理。"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from . import audit as audit_mod
from .db import DEFAULT_DB_PATH, init_schema, locked_db
from .passwords import hash_password, verify_password
from .policy import (
    ACTION_CATALOG,
    ROLE_PERMISSIONS,
    AuthzDecision,
    PolicySettings,
    Principal,
    SCOPE_ALL,
    TZ_TAIPEI,
    decide,
)

# 合成 Demo 帳號（書審／面試用；非正式憑證）
DEMO_ACCOUNTS: list[dict[str, Any]] = [
    {
        "user_id": "u-admin",
        "username": "admin",
        "password": "demo-admin-2026",
        "display_name": "黃雅婷（總部管理者）",
        "role": "admin",
        "home_store_id": "S01",
        "stores": [SCOPE_ALL],
    },
    {
        "user_id": "u-op-s01",
        "username": "operator.s01",
        "password": "demo-op-s01",
        "display_name": "林志偉（台北信義店營運）",
        "role": "operator",
        "home_store_id": "S01",
        "stores": ["S01"],
    },
    {
        "user_id": "u-op-north",
        "username": "operator.north",
        "password": "demo-op-north",
        "display_name": "陳佳蓉（北區營運）",
        "role": "operator",
        "home_store_id": "S01",
        "stores": ["S01", "S04"],
    },
    {
        "user_id": "u-op-s03",
        "username": "operator.s03",
        "password": "demo-op-s03",
        "display_name": "張書豪（高雄夢時代店營運）",
        "role": "operator",
        "home_store_id": "S03",
        "stores": ["S03"],
    },
    {
        "user_id": "u-view-s02",
        "username": "viewer.s02",
        "password": "demo-view-s02",
        "display_name": "吳佩珊（台中逢甲店檢視）",
        "role": "viewer",
        "home_store_id": "S02",
        "stores": ["S02"],
    },
]

DEFAULT_SETTINGS = {
    "high_impact_qty": "300",
    "business_hour_start": "9",
    "business_hour_end": "22",
    "stepup_minutes": "5",
}


class PermissionDenied(Exception):
    def __init__(self, decision: AuthzDecision):
        super().__init__(decision.reason)
        self.decision = decision


class ControlPlane:
    def __init__(self, db_path: Path | None = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH

    def ensure_ready(self) -> None:
        with locked_db(self.db_path) as conn:
            init_schema(conn)
            self._seed_if_empty(conn)

    def _seed_if_empty(self, conn: sqlite3.Connection) -> None:
        n = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        if n == 0:
            now = datetime.now(TZ_TAIPEI).isoformat(timespec="seconds")
            for acc in DEMO_ACCOUNTS:
                conn.execute(
                    """
                    INSERT INTO users(
                        user_id, username, display_name, password_hash,
                        home_store_id, is_active, created_at
                    ) VALUES (?, ?, ?, ?, ?, 1, ?)
                    """,
                    (
                        acc["user_id"],
                        acc["username"],
                        acc["display_name"],
                        hash_password(acc["password"]),
                        acc["home_store_id"],
                        now,
                    ),
                )
                conn.execute(
                    "INSERT INTO user_roles(user_id, role_id) VALUES (?, ?)",
                    (acc["user_id"], acc["role"]),
                )
                for sid in acc["stores"]:
                    conn.execute(
                        "INSERT INTO user_store_scopes(user_id, store_id) VALUES (?, ?)",
                        (acc["user_id"], sid),
                    )
            for k, v in DEFAULT_SETTINGS.items():
                conn.execute(
                    "INSERT OR IGNORE INTO settings(key, value, updated_by, updated_at) VALUES (?, ?, ?, ?)",
                    (k, v, "seed", now),
                )
            self._seed_sample_audit(conn, now)
        else:
            for k, v in DEFAULT_SETTINGS.items():
                conn.execute(
                    "INSERT OR IGNORE INTO settings(key, value, updated_by, updated_at) VALUES (?, ?, ?, ?)",
                    (k, v, "seed", datetime.now(TZ_TAIPEI).isoformat(timespec="seconds")),
                )

    def _seed_sample_audit(self, conn: sqlite3.Connection, now: str) -> None:
        """讓管理者儀表第一次開啟就看得到失敗授權與敏感成功樣本。"""
        samples = [
            {
                "ts": (datetime.now(TZ_TAIPEI) - timedelta(hours=6)).isoformat(timespec="seconds"),
                "request_id": "seed-deny-scope-1",
                "correlation_id": "seed-corr-1",
                "actor_id": "u-op-s01",
                "actor_username": "operator.s01",
                "actor_role": "operator",
                "action": "reorder.approve",
                "resource_type": "store",
                "resource_id": "S03",
                "store_id": "S03",
                "outcome": "deny",
                "risk_level": "medium",
                "risk_flags": "cross_store",
                "payload_summary": "嘗試核准高雄店補貨（種子事件）",
                "deny_reason": "門市 S03 不在你的資料範圍，跨店隔離生效。",
            },
            {
                "ts": (datetime.now(TZ_TAIPEI) - timedelta(hours=5)).isoformat(timespec="seconds"),
                "request_id": "seed-deny-perm-1",
                "correlation_id": "seed-corr-2",
                "actor_id": "u-view-s02",
                "actor_username": "viewer.s02",
                "actor_role": "viewer",
                "action": "inventory.write",
                "resource_type": "inventory",
                "resource_id": "S02:C01",
                "store_id": "S02",
                "outcome": "deny",
                "risk_level": "low",
                "risk_flags": "",
                "payload_summary": "檢視者嘗試調整庫存（種子事件）",
                "deny_reason": "角色「檢視者」缺少權限 inventory.write，預設拒絕。",
            },
            {
                "ts": (datetime.now(TZ_TAIPEI) - timedelta(hours=3)).isoformat(timespec="seconds"),
                "request_id": "seed-allow-reorder-1",
                "correlation_id": "seed-corr-3",
                "actor_id": "u-op-s01",
                "actor_username": "operator.s01",
                "actor_role": "operator",
                "action": "reorder.approve",
                "resource_type": "reorder_ticket",
                "resource_id": "seed-tkt-1",
                "store_id": "S01",
                "outcome": "allow",
                "risk_level": "medium",
                "risk_flags": "high_impact",
                "payload_summary": "核准台北信義店飲料補貨 420 件（種子事件）",
                "deny_reason": None,
            },
            {
                "ts": (datetime.now(TZ_TAIPEI) - timedelta(hours=2)).isoformat(timespec="seconds"),
                "request_id": "seed-allow-admin-1",
                "correlation_id": "seed-corr-4",
                "actor_id": "u-admin",
                "actor_username": "admin",
                "actor_role": "admin",
                "action": "settings.admin",
                "resource_type": "setting",
                "resource_id": "high_impact_qty",
                "store_id": None,
                "outcome": "allow",
                "risk_level": "low",
                "risk_flags": "",
                "payload_summary": "調整高影響門檻 280→300（種子事件）",
                "deny_reason": None,
            },
        ]
        for s in samples:
            conn.execute(
                """
                INSERT INTO audit_events (
                    timestamp, request_id, correlation_id, actor_id, actor_username,
                    actor_role, action, resource_type, resource_id, store_id, outcome,
                    risk_level, risk_flags, payload_summary, before_json, after_json,
                    deny_reason, session_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    s["ts"],
                    s["request_id"],
                    s["correlation_id"],
                    s["actor_id"],
                    s["actor_username"],
                    s["actor_role"],
                    s["action"],
                    s["resource_type"],
                    s["resource_id"],
                    s["store_id"],
                    s["outcome"],
                    s["risk_level"],
                    s["risk_flags"],
                    s["payload_summary"],
                    None,
                    None,
                    s["deny_reason"],
                    "seed-session",
                ),
            )

    def load_settings(self) -> PolicySettings:
        with locked_db(self.db_path) as conn:
            rows = {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM settings")}
        return PolicySettings(
            high_impact_qty=int(rows.get("high_impact_qty", DEFAULT_SETTINGS["high_impact_qty"])),
            business_hour_start=int(rows.get("business_hour_start", DEFAULT_SETTINGS["business_hour_start"])),
            business_hour_end=int(rows.get("business_hour_end", DEFAULT_SETTINGS["business_hour_end"])),
            stepup_minutes=int(rows.get("stepup_minutes", DEFAULT_SETTINGS["stepup_minutes"])),
        )

    def load_principal(
        self,
        user_id: str,
        *,
        session_id: str,
        last_stepup_at: datetime | None = None,
    ) -> Principal | None:
        with locked_db(self.db_path) as conn:
            user = conn.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
            if user is None:
                return None
            role_row = conn.execute(
                "SELECT role_id FROM user_roles WHERE user_id = ?", (user_id,)
            ).fetchone()
            stores = [
                r["store_id"]
                for r in conn.execute(
                    "SELECT store_id FROM user_store_scopes WHERE user_id = ?",
                    (user_id,),
                )
            ]
        role = role_row["role_id"] if role_row else "viewer"
        perms = ROLE_PERMISSIONS.get(role, frozenset())
        return Principal(
            user_id=user["user_id"],
            username=user["username"],
            display_name=user["display_name"],
            role=role,
            permissions=perms,
            store_scope=frozenset(stores),
            home_store_id=user["home_store_id"],
            session_id=session_id,
            last_stepup_at=last_stepup_at,
            is_active=bool(user["is_active"]),
        )

    def authenticate(
        self,
        username: str,
        password: str,
        *,
        session_id: str,
        correlation_id: str,
    ) -> tuple[Principal | None, str | None]:
        request_id = str(uuid.uuid4())
        now = datetime.now(TZ_TAIPEI)
        with locked_db(self.db_path) as conn:
            user = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username.strip(),)
            ).fetchone()
            ok = bool(
                user
                and user["is_active"]
                and verify_password(password, user["password_hash"])
            )
            if ok:
                audit_mod.record_event(
                    conn,
                    timestamp=now,
                    request_id=request_id,
                    correlation_id=correlation_id,
                    actor_id=user["user_id"],
                    actor_username=user["username"],
                    actor_role=None,
                    action="auth.login",
                    resource_type="session",
                    resource_id=session_id,
                    store_id=user["home_store_id"],
                    outcome="allow",
                    risk_level="low",
                    risk_flags=(),
                    payload_summary="登入成功",
                    before=None,
                    after=None,
                    deny_reason=None,
                    session_id=session_id,
                )
            else:
                audit_mod.record_event(
                    conn,
                    timestamp=now,
                    request_id=request_id,
                    correlation_id=correlation_id,
                    actor_id=None if user is None else user["user_id"],
                    actor_username=username.strip() or None,
                    actor_role=None,
                    action="auth.login",
                    resource_type="session",
                    resource_id=session_id,
                    store_id=None,
                    outcome="deny",
                    risk_level="medium",
                    risk_flags=(),
                    payload_summary="登入失敗",
                    before=None,
                    after=None,
                    deny_reason="帳號或密碼不正確，或帳號已停用。",
                    session_id=session_id,
                )
        if not ok:
            return None, "帳號或密碼不正確。"
        principal = self.load_principal(user["user_id"], session_id=session_id)
        return principal, None

    def record_logout(self, principal: Principal, correlation_id: str) -> None:
        now = datetime.now(TZ_TAIPEI)
        with locked_db(self.db_path) as conn:
            audit_mod.record_event(
                conn,
                timestamp=now,
                request_id=str(uuid.uuid4()),
                correlation_id=correlation_id,
                actor_id=principal.user_id,
                actor_username=principal.username,
                actor_role=principal.role,
                action="auth.logout",
                resource_type="session",
                resource_id=principal.session_id,
                store_id=principal.home_store_id,
                outcome="allow",
                risk_level="low",
                risk_flags=(),
                payload_summary="登出",
                before=None,
                after=None,
                deny_reason=None,
                session_id=principal.session_id,
            )

    def verify_stepup(self, principal: Principal, password: str, correlation_id: str) -> bool:
        request_id = str(uuid.uuid4())
        now = datetime.now(TZ_TAIPEI)
        with locked_db(self.db_path) as conn:
            user = conn.execute(
                "SELECT * FROM users WHERE user_id = ?", (principal.user_id,)
            ).fetchone()
            ok = bool(user and verify_password(password, user["password_hash"]))
            audit_mod.record_event(
                conn,
                timestamp=now,
                request_id=request_id,
                correlation_id=correlation_id,
                actor_id=principal.user_id,
                actor_username=principal.username,
                actor_role=principal.role,
                action="auth.stepup",
                resource_type="session",
                resource_id=principal.session_id,
                store_id=principal.home_store_id,
                outcome="allow" if ok else "deny",
                risk_level="low" if ok else "medium",
                risk_flags=(),
                payload_summary="再驗證成功" if ok else "再驗證失敗",
                before=None,
                after=None,
                deny_reason=None if ok else "再驗證密碼不正確。",
                session_id=principal.session_id,
            )
        return ok

    def authorize(
        self,
        principal: Principal | None,
        action: str,
        *,
        resource_type: str | None = None,
        resource_id: str | None = None,
        store_id: str | None = None,
        quantity: float | None = None,
        request_id: str | None = None,
        correlation_id: str = "",
        simulate_after_hours: bool = False,
        payload_summary: str = "",
        before: dict | None = None,
        after: dict | None = None,
        persist_audit: bool = True,
        audit_outcomes: tuple[str, ...] | None = None,
    ) -> AuthzDecision:
        settings = self.load_settings()
        now = datetime.now(TZ_TAIPEI)
        decision = decide(
            principal=principal,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            store_id=store_id,
            quantity=quantity,
            request_id=request_id or str(uuid.uuid4()),
            correlation_id=correlation_id,
            now=now,
            settings=settings,
            simulate_after_hours=simulate_after_hours,
            payload_summary=payload_summary,
            before=before,
            after=after,
        )
        should_audit = persist_audit and (
            audit_outcomes is None or decision.outcome in audit_outcomes
        )
        if should_audit:
            with locked_db(self.db_path) as conn:
                audit_mod.record_decision(conn, decision, now)
        return decision

    def enforce(self, *args, **kwargs) -> AuthzDecision:
        decision = self.authorize(*args, **kwargs)
        if not decision.allowed:
            raise PermissionDenied(decision)
        return decision

    def scoped_sales(self, df: pd.DataFrame, principal: Principal) -> pd.DataFrame:
        if principal.sees_all_stores:
            return df
        return df[df["store_id"].isin(principal.store_scope)].copy()

    def inventory_delta(self, store_id: str, category_id: str) -> int:
        with locked_db(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT COALESCE(SUM(delta), 0) AS s
                FROM inventory_adjustments
                WHERE store_id = ? AND category_id = ?
                """,
                (store_id, category_id),
            ).fetchone()
        return int(row["s"])

    def list_adjustments(self, store_ids: list[str] | None = None) -> list[dict[str, Any]]:
        if store_ids is not None and len(store_ids) == 0:
            return []
        with locked_db(self.db_path) as conn:
            if store_ids is None:
                rows = conn.execute(
                    "SELECT * FROM inventory_adjustments ORDER BY adj_id DESC LIMIT 200"
                ).fetchall()
            else:
                placeholders = ",".join("?" * len(store_ids))
                rows = conn.execute(
                    f"SELECT * FROM inventory_adjustments WHERE store_id IN ({placeholders}) ORDER BY adj_id DESC LIMIT 200",
                    store_ids,
                ).fetchall()
        return [dict(r) for r in rows]

    def adjust_inventory(
        self,
        principal: Principal,
        *,
        store_id: str,
        category_id: str,
        delta: int,
        reason: str,
        correlation_id: str,
        simulate_after_hours: bool = False,
        base_inventory: float = 0.0,
    ) -> AuthzDecision:
        before = {"inventory_end": round(float(base_inventory), 1)}
        after = {"inventory_end": round(float(base_inventory) + int(delta), 1)}
        summary = f"調整庫存 {store_id}/{category_id} delta={int(delta):+d}（{reason}）"
        decision = self.authorize(
            principal,
            "inventory.write",
            resource_type="inventory",
            resource_id=f"{store_id}:{category_id}",
            store_id=store_id,
            quantity=float(delta),
            correlation_id=correlation_id,
            simulate_after_hours=simulate_after_hours,
            payload_summary=summary,
            before=before,
            after=after,
        )
        if not decision.allowed:
            return decision
        now = datetime.now(TZ_TAIPEI).isoformat(timespec="seconds")
        with locked_db(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO inventory_adjustments(
                    store_id, category_id, delta, reason, actor_id, request_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    store_id,
                    category_id,
                    int(delta),
                    reason,
                    principal.user_id,
                    decision.request_id,
                    now,
                ),
            )
        return decision

    def list_tickets(self, store_ids: list[str] | None = None) -> list[dict[str, Any]]:
        if store_ids is not None and len(store_ids) == 0:
            return []
        with locked_db(self.db_path) as conn:
            if store_ids is None:
                rows = conn.execute(
                    "SELECT * FROM reorder_tickets ORDER BY created_at DESC LIMIT 200"
                ).fetchall()
            else:
                placeholders = ",".join("?" * len(store_ids))
                rows = conn.execute(
                    f"SELECT * FROM reorder_tickets WHERE store_id IN ({placeholders}) ORDER BY created_at DESC LIMIT 200",
                    store_ids,
                ).fetchall()
        return [dict(r) for r in rows]

    def get_ticket(self, ticket_id: str) -> dict[str, Any] | None:
        with locked_db(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM reorder_tickets WHERE ticket_id = ?", (ticket_id,)
            ).fetchone()
        return dict(row) if row else None

    def create_reorder(
        self,
        principal: Principal,
        *,
        store_id: str,
        category_id: str,
        qty: int,
        correlation_id: str,
        simulate_after_hours: bool = False,
        note: str = "",
    ) -> tuple[AuthzDecision, str | None]:
        ticket_id = str(uuid.uuid4())[:8]
        preview = decide(
            principal=principal,
            action="reorder.request",
            resource_type="reorder_ticket",
            resource_id=ticket_id,
            store_id=store_id,
            quantity=float(qty),
            now=datetime.now(TZ_TAIPEI),
            settings=self.load_settings(),
            simulate_after_hours=simulate_after_hours,
        )
        summary = f"提出補貨 {store_id}/{category_id} 建議量 {int(qty)} 件"
        decision = self.authorize(
            principal,
            "reorder.request",
            resource_type="reorder_ticket",
            resource_id=ticket_id,
            store_id=store_id,
            quantity=float(qty),
            correlation_id=correlation_id,
            simulate_after_hours=simulate_after_hours,
            payload_summary=summary,
            after={
                "ticket_id": ticket_id,
                "qty": int(qty),
                "risk": preview.risk.level,
                "flags": list(preview.risk.flags),
            },
        )
        if not decision.allowed:
            return decision, None
        now = datetime.now(TZ_TAIPEI).isoformat(timespec="seconds")
        with locked_db(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO reorder_tickets(
                    ticket_id, store_id, category_id, recommended_qty, status,
                    risk_level, risk_flags, created_by, decided_by, created_at,
                    decided_at, request_id, note
                ) VALUES (?, ?, ?, ?, 'pending', ?, ?, ?, NULL, ?, NULL, ?, ?)
                """,
                (
                    ticket_id,
                    store_id,
                    category_id,
                    int(qty),
                    preview.risk.level,
                    ",".join(preview.risk.flags),
                    principal.user_id,
                    now,
                    decision.request_id,
                    note,
                ),
            )
        return decision, ticket_id

    def decide_reorder(
        self,
        principal: Principal,
        *,
        ticket_id: str,
        approve: bool,
        correlation_id: str,
        simulate_after_hours: bool = False,
    ) -> AuthzDecision:
        ticket = self.get_ticket(ticket_id)
        if ticket is None:
            decision = self.authorize(
                principal,
                "reorder.approve",
                resource_type="reorder_ticket",
                resource_id=ticket_id,
                store_id=None,
                correlation_id=correlation_id,
                payload_summary="補貨單不存在",
            )
            return decision
        before = {"status": ticket["status"]}
        new_status = "approved" if approve else "rejected"
        after = {"status": new_status, "decided_by": principal.username}
        verb = "核准" if approve else "駁回"
        summary = (
            f"{verb}補貨 {ticket['store_id']}/{ticket['category_id']} "
            f"{ticket['recommended_qty']} 件"
        )
        decision = self.authorize(
            principal,
            "reorder.approve",
            resource_type="reorder_ticket",
            resource_id=ticket_id,
            store_id=ticket["store_id"],
            quantity=float(ticket["recommended_qty"]),
            correlation_id=correlation_id,
            simulate_after_hours=simulate_after_hours,
            payload_summary=summary,
            before=before,
            after=after,
        )
        if not decision.allowed:
            return decision
        now = datetime.now(TZ_TAIPEI).isoformat(timespec="seconds")
        with locked_db(self.db_path) as conn:
            conn.execute(
                """
                UPDATE reorder_tickets
                SET status = ?, decided_by = ?, decided_at = ?
                WHERE ticket_id = ? AND status = 'pending'
                """,
                (new_status, principal.user_id, now, ticket_id),
            )
        return decision

    def update_setting(
        self,
        principal: Principal,
        key: str,
        value: str,
        *,
        correlation_id: str,
    ) -> AuthzDecision:
        allowed_keys = set(DEFAULT_SETTINGS)
        if key not in allowed_keys:
            return self.authorize(
                principal,
                "settings.admin",
                resource_type="setting",
                resource_id=key,
                correlation_id=correlation_id,
                payload_summary=f"未知設定鍵 {key}",
            )
        with locked_db(self.db_path) as conn:
            old = conn.execute(
                "SELECT value FROM settings WHERE key = ?", (key,)
            ).fetchone()
        before = {key: None if old is None else old["value"]}
        after = {key: str(value)}
        decision = self.authorize(
            principal,
            "settings.admin",
            resource_type="setting",
            resource_id=key,
            correlation_id=correlation_id,
            payload_summary=f"設定 {key}：{before[key]} → {value}",
            before=before,
            after=after,
        )
        if not decision.allowed:
            return decision
        now = datetime.now(TZ_TAIPEI).isoformat(timespec="seconds")
        with locked_db(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO settings(key, value, updated_by, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_by = excluded.updated_by,
                    updated_at = excluded.updated_at
                """,
                (key, str(value), principal.user_id, now),
            )
        return decision

    def list_users(self) -> list[dict[str, Any]]:
        with locked_db(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT u.*, r.role_id AS role
                FROM users u
                LEFT JOIN user_roles r ON r.user_id = u.user_id
                ORDER BY u.username
                """
            ).fetchall()
            scopes: dict[str, list[str]] = {}
            for s in conn.execute("SELECT user_id, store_id FROM user_store_scopes"):
                scopes.setdefault(s["user_id"], []).append(s["store_id"])
        out = []
        for r in rows:
            d = dict(r)
            d["stores"] = sorted(scopes.get(d["user_id"], []))
            out.append(d)
        return out

    def update_user(
        self,
        principal: Principal,
        *,
        target_user_id: str,
        role: str,
        stores: list[str],
        is_active: bool,
        correlation_id: str,
    ) -> AuthzDecision:
        if role not in ROLE_PERMISSIONS:
            raise ValueError(f"unknown role: {role}")
        users = {u["user_id"]: u for u in self.list_users()}
        target = users.get(target_user_id)
        if target is None:
            return self.authorize(
                principal,
                "user.admin",
                resource_type="user",
                resource_id=target_user_id,
                correlation_id=correlation_id,
                payload_summary="目標帳號不存在",
            )
        before = {
            "role": target["role"],
            "stores": target["stores"],
            "is_active": bool(target["is_active"]),
        }
        after = {"role": role, "stores": list(stores), "is_active": bool(is_active)}
        admin_count = sum(1 for u in users.values() if u["role"] == "admin" and u["is_active"])
        would_drop_last_admin = (
            target["role"] == "admin"
            and bool(target["is_active"])
            and (role != "admin" or not is_active)
            and admin_count <= 1
        )
        decision = self.authorize(
            principal,
            "user.admin",
            resource_type="user",
            resource_id=target_user_id,
            correlation_id=correlation_id,
            payload_summary=(
                "拒絕：不可停用或降級最後一位管理者"
                if would_drop_last_admin
                else f"變更帳號 {target['username']} 角色／範圍"
            ),
            before=before,
            after=after,
            persist_audit=False,
        )
        if would_drop_last_admin and decision.allowed:
            decision.allowed = False
            decision.outcome = "deny"
            decision.reason_code = "LAST_ADMIN"
            decision.reason = "不可停用或降級最後一位管理者。"
        with locked_db(self.db_path) as conn:
            audit_mod.record_decision(conn, decision, datetime.now(TZ_TAIPEI))
        if not decision.allowed:
            return decision
        if not decision.allowed:
            return decision
        with locked_db(self.db_path) as conn:
            conn.execute(
                "UPDATE users SET is_active = ? WHERE user_id = ?",
                (1 if is_active else 0, target_user_id),
            )
            conn.execute("DELETE FROM user_roles WHERE user_id = ?", (target_user_id,))
            conn.execute(
                "INSERT INTO user_roles(user_id, role_id) VALUES (?, ?)",
                (target_user_id, role),
            )
            conn.execute("DELETE FROM user_store_scopes WHERE user_id = ?", (target_user_id,))
            for sid in stores:
                conn.execute(
                    "INSERT INTO user_store_scopes(user_id, store_id) VALUES (?, ?)",
                    (target_user_id, sid),
                )
        return decision

    def query_audit(self, **kwargs) -> list[dict[str, Any]]:
        with locked_db(self.db_path) as conn:
            return audit_mod.query_events(conn, **kwargs)

    def audit_stats(self, hours: int = 24) -> dict[str, int]:
        since = (datetime.now(TZ_TAIPEI) - timedelta(hours=hours)).isoformat(timespec="seconds")
        with locked_db(self.db_path) as conn:
            return audit_mod.dashboard_stats(conn, since)

    def export_audit_csv(self, rows: list[dict[str, Any]]) -> str:
        return audit_mod.export_csv(rows)


_DEFAULT: ControlPlane | None = None


def get_control_plane(db_path: Path | None = None) -> ControlPlane:
    global _DEFAULT
    if db_path is not None:
        cp = ControlPlane(db_path)
        cp.ensure_ready()
        return cp
    if _DEFAULT is None:
        _DEFAULT = ControlPlane()
        _DEFAULT.ensure_ready()
    return _DEFAULT


def permission_label(action: str) -> str:
    return ACTION_CATALOG.get(action, action)


def risk_flag_label(flag: str) -> str:
    return {
        "after_hours": "非營業時間",
        "high_impact": "高影響核准",
        "cross_store": "跨店核准",
    }.get(flag, flag)
