# -*- coding: utf-8 -*-
"""追加寫入稽核：寫入、查詢、匯出。禁止更新／刪除。"""

from __future__ import annotations

import csv
import io
import json
import sqlite3
from datetime import datetime
from typing import Any, Iterable

from .policy import AuthzDecision, TZ_TAIPEI

AUDIT_COLUMNS = [
    "event_id",
    "timestamp",
    "request_id",
    "correlation_id",
    "actor_id",
    "actor_username",
    "actor_role",
    "action",
    "resource_type",
    "resource_id",
    "store_id",
    "outcome",
    "risk_level",
    "risk_flags",
    "payload_summary",
    "before_json",
    "after_json",
    "deny_reason",
    "session_id",
]


def _json_dump(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, default=str)


def record_event(
    conn: sqlite3.Connection,
    *,
    timestamp: datetime,
    request_id: str,
    correlation_id: str,
    actor_id: str | None,
    actor_username: str | None,
    actor_role: str | None,
    action: str,
    resource_type: str | None,
    resource_id: str | None,
    store_id: str | None,
    outcome: str,
    risk_level: str | None,
    risk_flags: Iterable[str] | str | None,
    payload_summary: str | None,
    before: dict | None,
    after: dict | None,
    deny_reason: str | None,
    session_id: str | None,
) -> int:
    if isinstance(risk_flags, str):
        flags_s = risk_flags
    elif risk_flags:
        flags_s = ",".join(risk_flags)
    else:
        flags_s = ""
    ts = timestamp.astimezone(TZ_TAIPEI).isoformat(timespec="seconds")
    cur = conn.execute(
        """
        INSERT INTO audit_events (
            timestamp, request_id, correlation_id, actor_id, actor_username,
            actor_role, action, resource_type, resource_id, store_id, outcome,
            risk_level, risk_flags, payload_summary, before_json, after_json,
            deny_reason, session_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            ts,
            request_id,
            correlation_id,
            actor_id,
            actor_username,
            actor_role,
            action,
            resource_type,
            resource_id,
            store_id,
            outcome,
            risk_level,
            flags_s,
            payload_summary or "",
            _json_dump(before),
            _json_dump(after),
            deny_reason,
            session_id,
        ),
    )
    return int(cur.lastrowid)


def record_decision(
    conn: sqlite3.Connection,
    decision: AuthzDecision,
    timestamp: datetime,
) -> int:
    p = decision.principal
    deny = None if decision.allowed else decision.reason
    return record_event(
        conn,
        timestamp=timestamp,
        request_id=decision.request_id,
        correlation_id=decision.correlation_id,
        actor_id=None if p is None else p.user_id,
        actor_username=None if p is None else p.username,
        actor_role=None if p is None else p.role,
        action=decision.action,
        resource_type=decision.resource_type,
        resource_id=decision.resource_id,
        store_id=decision.store_id,
        outcome=decision.outcome,
        risk_level=decision.risk.level,
        risk_flags=decision.risk.flags,
        payload_summary=decision.payload_summary,
        before=decision.before,
        after=decision.after,
        deny_reason=deny,
        session_id=None if p is None else p.session_id,
    )


def query_events(
    conn: sqlite3.Connection,
    *,
    actor: str | None = None,
    action: str | None = None,
    outcome: str | None = None,
    store_id: str | None = None,
    request_id: str | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if actor:
        clauses.append("actor_username = ?")
        params.append(actor)
    if action:
        clauses.append("action = ?")
        params.append(action)
    if outcome:
        clauses.append("outcome = ?")
        params.append(outcome)
    if store_id:
        clauses.append("store_id = ?")
        params.append(store_id)
    if request_id:
        clauses.append("(request_id = ? OR correlation_id = ?)")
        params.extend([request_id, request_id])
    if since:
        clauses.append("timestamp >= ?")
        params.append(since)
    if until:
        clauses.append("timestamp <= ?")
        params.append(until)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"""
        SELECT * FROM audit_events
        {where}
        ORDER BY event_id DESC
        LIMIT ?
    """
    params.append(int(limit))
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def dashboard_stats(conn: sqlite3.Connection, since_iso: str) -> dict[str, int]:
    def count(sql: str, params: tuple = ()) -> int:
        row = conn.execute(sql, params).fetchone()
        return int(row[0]) if row else 0

    return {
        "deny_recent": count(
            "SELECT COUNT(*) FROM audit_events WHERE outcome = 'deny' AND timestamp >= ?",
            (since_iso,),
        ),
        "challenge_recent": count(
            "SELECT COUNT(*) FROM audit_events WHERE outcome = 'challenge' AND timestamp >= ?",
            (since_iso,),
        ),
        "sensitive_allow_recent": count(
            """
            SELECT COUNT(*) FROM audit_events
            WHERE outcome = 'allow'
              AND timestamp >= ?
              AND action IN ('inventory.write','reorder.approve','settings.admin','user.admin','model.retrain')
            """,
            (since_iso,),
        ),
        "high_risk_recent": count(
            "SELECT COUNT(*) FROM audit_events WHERE risk_level = 'high' AND timestamp >= ?",
            (since_iso,),
        ),
        "total": count("SELECT COUNT(*) FROM audit_events"),
    }


def export_csv(rows: list[dict[str, Any]]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=AUDIT_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row.get(k, "") for k in AUDIT_COLUMNS})
    return buf.getvalue()
