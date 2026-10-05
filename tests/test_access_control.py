# -*- coding: utf-8 -*-
"""RBAC／細粒度授權、門市範圍、稽核追加寫入、存取風險 — 非攻擊測試。"""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from src.access.control import ControlPlane, DEMO_ACCOUNTS
from src.access.db import connect
from src.access.policy import (
    PolicySettings,
    Principal,
    TZ_TAIPEI,
    assess_access_risk,
    decide,
)
from src.recommend import replenishment_need
import pandas as pd


def _cp(tmp: str) -> ControlPlane:
    plane = ControlPlane(Path(tmp) / "ops.db")
    plane.ensure_ready()
    return plane


def _login(plane: ControlPlane, username: str, password: str) -> Principal:
    p, err = plane.authenticate(
        username, password, session_id="sess-test", correlation_id="corr-test"
    )
    assert err is None, err
    assert p is not None
    return p


def _with_stepup(p: Principal) -> Principal:
    return Principal(
        user_id=p.user_id,
        username=p.username,
        display_name=p.display_name,
        role=p.role,
        permissions=p.permissions,
        store_scope=p.store_scope,
        home_store_id=p.home_store_id,
        session_id=p.session_id,
        last_stepup_at=datetime.now(TZ_TAIPEI),
        is_active=p.is_active,
    )


class PolicyTests(unittest.TestCase):
    def test_default_deny_unknown_action(self):
        p = Principal(
            user_id="x",
            username="x",
            display_name="x",
            role="admin",
            permissions=frozenset({"forecast.read"}),
            store_scope=frozenset({"*"}),
            home_store_id="S01",
            session_id="s",
        )
        d = decide(principal=p, action="not.a.real.action", store_id="S01")
        self.assertFalse(d.allowed)
        self.assertEqual(d.outcome, "deny")
        self.assertEqual(d.reason_code, "UNKNOWN_ACTION")

    def test_unauthenticated_denied(self):
        d = decide(principal=None, action="forecast.read", store_id="S01")
        self.assertFalse(d.allowed)
        self.assertEqual(d.reason_code, "UNAUTHENTICATED")

    def test_viewer_cannot_write_inventory(self):
        from src.access.policy import ROLE_PERMISSIONS

        p = Principal(
            user_id="v",
            username="viewer.s02",
            display_name="v",
            role="viewer",
            permissions=ROLE_PERMISSIONS["viewer"],
            store_scope=frozenset({"S02"}),
            home_store_id="S02",
            session_id="s",
        )
        d = decide(
            principal=p,
            action="inventory.write",
            store_id="S02",
            quantity=10,
        )
        self.assertFalse(d.allowed)
        self.assertEqual(d.reason_code, "PERMISSION_DENIED")

    def test_operator_scope_isolation(self):
        from src.access.policy import ROLE_PERMISSIONS

        p = Principal(
            user_id="o",
            username="operator.s01",
            display_name="o",
            role="operator",
            permissions=ROLE_PERMISSIONS["operator"],
            store_scope=frozenset({"S01"}),
            home_store_id="S01",
            session_id="s",
            last_stepup_at=datetime.now(TZ_TAIPEI),
        )
        allow = decide(
            principal=p, action="reorder.approve", store_id="S01", quantity=10
        )
        deny = decide(
            principal=p, action="reorder.approve", store_id="S03", quantity=10
        )
        self.assertTrue(allow.allowed)
        self.assertFalse(deny.allowed)
        self.assertEqual(deny.reason_code, "SCOPE_DENIED")

    def test_stepup_challenge_for_high_impact_approve(self):
        from src.access.policy import ROLE_PERMISSIONS

        p = Principal(
            user_id="o",
            username="operator.s01",
            display_name="o",
            role="operator",
            permissions=ROLE_PERMISSIONS["operator"],
            store_scope=frozenset({"S01"}),
            home_store_id="S01",
            session_id="s",
            last_stepup_at=None,
        )
        d = decide(
            principal=p,
            action="reorder.approve",
            store_id="S01",
            quantity=500,
            settings=PolicySettings(high_impact_qty=300),
        )
        self.assertFalse(d.allowed)
        self.assertEqual(d.outcome, "challenge")
        self.assertEqual(d.reason_code, "STEPUP_REQUIRED")
        self.assertIn("high_impact", d.risk.flags)

    def test_admin_only_action_rejected_for_operator(self):
        from src.access.policy import ROLE_PERMISSIONS

        p = Principal(
            user_id="o",
            username="operator.s01",
            display_name="o",
            role="operator",
            permissions=ROLE_PERMISSIONS["operator"] | frozenset({"settings.admin"}),
            store_scope=frozenset({"S01"}),
            home_store_id="S01",
            session_id="s",
            last_stepup_at=datetime.now(TZ_TAIPEI),
        )
        d = decide(principal=p, action="settings.admin")
        self.assertFalse(d.allowed)
        self.assertEqual(d.reason_code, "ADMIN_SESSION_REQUIRED")


class RiskTests(unittest.TestCase):
    def test_after_hours_and_cross_store_flags(self):
        from src.access.policy import ROLE_PERMISSIONS

        p = Principal(
            user_id="a",
            username="admin",
            display_name="a",
            role="admin",
            permissions=ROLE_PERMISSIONS["admin"],
            store_scope=frozenset({"*"}),
            home_store_id="S01",
            session_id="s",
        )
        night = datetime(2026, 3, 1, 23, 30, tzinfo=TZ_TAIPEI)
        risk = assess_access_risk(
            action="reorder.approve",
            principal=p,
            store_id="S03",
            quantity=400,
            now=night,
            settings=PolicySettings(high_impact_qty=300, business_hour_start=9, business_hour_end=22),
        )
        self.assertIn("after_hours", risk.flags)
        self.assertIn("cross_store", risk.flags)
        self.assertIn("high_impact", risk.flags)
        self.assertEqual(risk.level, "high")

    def test_simulate_after_hours(self):
        risk = assess_access_risk(
            action="inventory.write",
            principal=None,
            store_id="S01",
            quantity=1,
            now=datetime(2026, 3, 1, 12, 0, tzinfo=TZ_TAIPEI),
            settings=PolicySettings(),
            simulate_after_hours=True,
        )
        self.assertIn("after_hours", risk.flags)


class ControlPlaneTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.plane = _cp(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_demo_login_and_wrong_password_audited(self):
        p, err = self.plane.authenticate(
            "admin", "demo-admin-2026", session_id="s", correlation_id="c"
        )
        self.assertIsNone(err)
        self.assertEqual(p.role, "admin")
        bad, err2 = self.plane.authenticate(
            "admin", "wrong-password", session_id="s", correlation_id="c"
        )
        self.assertIsNone(bad)
        self.assertIsNotNone(err2)
        rows = self.plane.query_audit(action="auth.login")
        outcomes = {r["outcome"] for r in rows}
        self.assertIn("allow", outcomes)
        self.assertIn("deny", outcomes)

    def test_store_scope_on_dataframe(self):
        df = pd.DataFrame(
            {
                "store_id": ["S01", "S02", "S03", "S04"],
                "sales_qty": [1, 2, 3, 4],
            }
        )
        op = _login(self.plane, "operator.s01", "demo-op-s01")
        north = _login(self.plane, "operator.north", "demo-op-north")
        admin = _login(self.plane, "admin", "demo-admin-2026")
        self.assertEqual(list(self.plane.scoped_sales(df, op)["store_id"]), ["S01"])
        self.assertEqual(list(self.plane.scoped_sales(df, north)["store_id"]), ["S01", "S04"])
        self.assertEqual(len(self.plane.scoped_sales(df, admin)), 4)

    def test_cross_store_reorder_denied_and_audited(self):
        op = _login(self.plane, "operator.s01", "demo-op-s01")
        d, tid = self.plane.create_reorder(
            op, store_id="S03", category_id="C01", qty=20, correlation_id="c"
        )
        self.assertIsNone(tid)
        self.assertFalse(d.allowed)
        self.assertEqual(d.reason_code, "SCOPE_DENIED")
        rows = self.plane.query_audit(action="reorder.request", outcome="deny")
        self.assertTrue(any(r["store_id"] == "S03" for r in rows))

    def test_inventory_adjust_roundtrip_and_before_after(self):
        op = _with_stepup(_login(self.plane, "operator.s01", "demo-op-s01"))
        d = self.plane.adjust_inventory(
            op,
            store_id="S01",
            category_id="C01",
            delta=12,
            reason="盤點",
            correlation_id="c",
            base_inventory=100,
        )
        self.assertTrue(d.allowed, d.reason)
        self.assertEqual(self.plane.inventory_delta("S01", "C01"), 12)
        rows = self.plane.query_audit(action="inventory.write", outcome="allow")
        self.assertTrue(rows)
        self.assertIn("100", rows[0]["before_json"] or "")
        self.assertIn("112", rows[0]["after_json"] or "")

    def test_high_impact_inventory_requires_stepup(self):
        op = _login(self.plane, "operator.s01", "demo-op-s01")
        d = self.plane.adjust_inventory(
            op,
            store_id="S01",
            category_id="C01",
            delta=500,
            reason="大盤盈",
            correlation_id="c",
            base_inventory=10,
        )
        self.assertFalse(d.allowed)
        self.assertEqual(d.outcome, "challenge")
        self.assertEqual(self.plane.inventory_delta("S01", "C01"), 0)

    def test_reorder_approve_flow(self):
        op = _with_stepup(_login(self.plane, "operator.s01", "demo-op-s01"))
        d, tid = self.plane.create_reorder(
            op, store_id="S01", category_id="C02", qty=40, correlation_id="c"
        )
        self.assertTrue(d.allowed, d.reason)
        self.assertIsNotNone(tid)
        ad = self.plane.decide_reorder(
            op, ticket_id=tid, approve=True, correlation_id="c"
        )
        self.assertTrue(ad.allowed, ad.reason)
        t = self.plane.get_ticket(tid)
        self.assertEqual(t["status"], "approved")

    def test_viewer_cannot_approve(self):
        viewer = _with_stepup(_login(self.plane, "viewer.s02", "demo-view-s02"))
        d, tid = self.plane.create_reorder(
            viewer, store_id="S02", category_id="C01", qty=10, correlation_id="c"
        )
        self.assertFalse(d.allowed)
        self.assertIsNone(tid)

    def test_audit_append_only(self):
        conn = connect(self.plane.db_path)
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("UPDATE audit_events SET outcome = 'tamper' WHERE event_id = 1")
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("DELETE FROM audit_events WHERE event_id = 1")
        finally:
            conn.close()

    def test_audit_filter_and_export_columns(self):
        rows = self.plane.query_audit(outcome="deny", limit=50)
        self.assertTrue(rows)
        csv_text = self.plane.export_audit_csv(rows)
        header = csv_text.splitlines()[0]
        for col in [
            "actor_username",
            "action",
            "resource_id",
            "outcome",
            "timestamp",
            "request_id",
            "correlation_id",
        ]:
            self.assertIn(col, header)

    def test_settings_admin_requires_stepup(self):
        admin = _login(self.plane, "admin", "demo-admin-2026")
        d = self.plane.update_setting(
            admin, "high_impact_qty", "250", correlation_id="c"
        )
        self.assertFalse(d.allowed)
        self.assertEqual(d.reason_code, "STEPUP_REQUIRED")
        admin2 = _with_stepup(admin)
        d2 = self.plane.update_setting(
            admin2, "high_impact_qty", "250", correlation_id="c"
        )
        self.assertTrue(d2.allowed, d2.reason)
        self.assertEqual(self.plane.load_settings().high_impact_qty, 250)

    def test_operator_cannot_change_role(self):
        op = _with_stepup(_login(self.plane, "operator.s01", "demo-op-s01"))
        d = self.plane.update_user(
            op,
            target_user_id="u-view-s02",
            role="admin",
            stores=["*"],
            is_active=True,
            correlation_id="c",
        )
        self.assertFalse(d.allowed)
        self.assertIn(d.reason_code, {"PERMISSION_DENIED", "ADMIN_SESSION_REQUIRED"})

    def test_cannot_drop_last_admin(self):
        admin = _with_stepup(_login(self.plane, "admin", "demo-admin-2026"))
        d = self.plane.update_user(
            admin,
            target_user_id="u-admin",
            role="viewer",
            stores=["S01"],
            is_active=True,
            correlation_id="c",
        )
        self.assertFalse(d.allowed)
        self.assertEqual(d.reason_code, "LAST_ADMIN")

    def test_stepup_password(self):
        admin = _login(self.plane, "admin", "demo-admin-2026")
        self.assertTrue(self.plane.verify_stepup(admin, "demo-admin-2026", "c"))
        self.assertFalse(self.plane.verify_stepup(admin, "nope", "c"))
        rows = self.plane.query_audit(action="auth.stepup")
        self.assertTrue(any(r["outcome"] == "deny" for r in rows))

    def test_dashboard_stats_keys(self):
        stats = self.plane.audit_stats(hours=24)
        for k in ("deny_recent", "sensitive_allow_recent", "high_risk_recent", "total"):
            self.assertIn(k, stats)
        self.assertGreaterEqual(stats["deny_recent"], 1)
        self.assertGreaterEqual(stats["sensitive_allow_recent"], 1)

    def test_seed_passwords_documented(self):
        names = {a["username"] for a in DEMO_ACCOUNTS}
        self.assertEqual(
            names,
            {"admin", "operator.s01", "operator.north", "operator.s03", "viewer.s02"},
        )


class RecommendHelperTests(unittest.TestCase):
    def test_replenishment_need(self):
        fc = pd.DataFrame({"pred_rf": [10, 10, 10, 10, 10]})
        need, gap = replenishment_need(fc, recent_inventory=10, lead_time_days=2, service_buffer=0.2)
        self.assertGreater(need, 0)
        self.assertEqual(gap, need - 10)


if __name__ == "__main__":
    unittest.main()
