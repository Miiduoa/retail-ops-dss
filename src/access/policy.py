# -*- coding: utf-8 -*-
"""
細粒度授權（PDP）：資源＋動作、預設拒絕、門市範圍、敏感操作再驗證。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Iterable
from zoneinfo import ZoneInfo

TZ_TAIPEI = ZoneInfo("Asia/Taipei")

# 資源.動作：授權的最小單位。未列在目錄者一律拒絕。
ACTION_CATALOG: dict[str, str] = {
    "auth.login": "登入（稽核事件，非授權標的）",
    "auth.logout": "登出",
    "auth.stepup": "工作階段再驗證",
    "dashboard.read": "檢視資料概覽",
    "forecast.read": "檢視需求預測與建議",
    "eval.read": "檢視模型評估",
    "inventory.read": "檢視庫存",
    "inventory.write": "調整庫存",
    "reorder.read": "檢視補貨申請",
    "reorder.request": "提出補貨申請",
    "reorder.approve": "核准或駁回補貨",
    "staffing.recommend": "檢視人力建議",
    "audit.read": "檢視操作稽核",
    "audit.export": "匯出稽核摘要",
    "settings.admin": "變更系統設定",
    "user.admin": "變更帳號角色或門市範圍",
    "model.retrain": "重新訓練預測模型",
}

STORE_SCOPED_ACTIONS = frozenset(
    {
        "dashboard.read",
        "forecast.read",
        "inventory.read",
        "inventory.write",
        "reorder.read",
        "reorder.request",
        "reorder.approve",
        "staffing.recommend",
    }
)

# 僅管理者工作階段可執行（即使誤授 permission 字串也不放行）
ADMIN_ONLY_ACTIONS = frozenset({"settings.admin", "user.admin", "audit.export"})

SENSITIVE_ACTIONS = frozenset(
    {
        "inventory.write",
        "reorder.approve",
        "settings.admin",
        "user.admin",
        "model.retrain",
    }
)

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "viewer": frozenset(
        {
            "dashboard.read",
            "forecast.read",
            "eval.read",
            "inventory.read",
            "reorder.read",
            "staffing.recommend",
        }
    ),
    "operator": frozenset(
        {
            "dashboard.read",
            "forecast.read",
            "eval.read",
            "inventory.read",
            "inventory.write",
            "reorder.read",
            "reorder.request",
            "reorder.approve",
            "staffing.recommend",
        }
    ),
    "admin": frozenset(
        {
            "dashboard.read",
            "forecast.read",
            "eval.read",
            "inventory.read",
            "inventory.write",
            "reorder.read",
            "reorder.request",
            "reorder.approve",
            "staffing.recommend",
            "audit.read",
            "audit.export",
            "settings.admin",
            "user.admin",
            "model.retrain",
        }
    ),
}

ROLE_LABELS = {
    "viewer": "檢視者",
    "operator": "門市營運",
    "admin": "系統管理者",
}

SCOPE_ALL = "*"

REASON_UNAUTHENTICATED = "UNAUTHENTICATED"
REASON_UNKNOWN_ACTION = "UNKNOWN_ACTION"
REASON_PERMISSION_DENIED = "PERMISSION_DENIED"
REASON_SCOPE_DENIED = "SCOPE_DENIED"
REASON_ADMIN_SESSION_REQUIRED = "ADMIN_SESSION_REQUIRED"
REASON_STEPUP_REQUIRED = "STEPUP_REQUIRED"
REASON_INACTIVE = "INACTIVE"
REASON_ALLOW = "ALLOW"


@dataclass(frozen=True)
class Principal:
    user_id: str
    username: str
    display_name: str
    role: str
    permissions: frozenset[str]
    store_scope: frozenset[str]
    home_store_id: str | None
    session_id: str
    last_stepup_at: datetime | None = None
    is_active: bool = True

    @property
    def role_label(self) -> str:
        return ROLE_LABELS.get(self.role, self.role)

    @property
    def sees_all_stores(self) -> bool:
        return SCOPE_ALL in self.store_scope

    def allowed_store_ids(self, all_store_ids: Iterable[str]) -> list[str]:
        ids = list(all_store_ids)
        if self.sees_all_stores:
            return ids
        allowed = set(self.store_scope)
        return [s for s in ids if s in allowed]

    def in_store_scope(self, store_id: str | None) -> bool:
        if store_id is None:
            return False
        if self.sees_all_stores:
            return True
        return store_id in self.store_scope

    def stepup_is_fresh(self, now: datetime, max_age: timedelta) -> bool:
        if self.last_stepup_at is None:
            return False
        ts = self.last_stepup_at
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=TZ_TAIPEI)
        return (now - ts) <= max_age


@dataclass(frozen=True)
class RiskAssessment:
    level: str  # low / medium / high
    flags: tuple[str, ...]
    messages: tuple[str, ...]

    @property
    def is_elevated(self) -> bool:
        return self.level in {"medium", "high"}


@dataclass
class AuthzDecision:
    allowed: bool
    outcome: str  # allow / deny / challenge
    reason_code: str
    reason: str
    action: str
    principal: Principal | None
    resource_type: str | None = None
    resource_id: str | None = None
    store_id: str | None = None
    request_id: str = ""
    correlation_id: str = ""
    risk: RiskAssessment = field(
        default_factory=lambda: RiskAssessment("low", (), ())
    )
    require_stepup: bool = False
    quantity: float | None = None
    payload_summary: str = ""
    before: dict | None = None
    after: dict | None = None


@dataclass(frozen=True)
class PolicySettings:
    high_impact_qty: int = 300
    business_hour_start: int = 9
    business_hour_end: int = 22
    stepup_minutes: int = 5


def assess_access_risk(
    *,
    action: str,
    principal: Principal | None,
    store_id: str | None,
    quantity: float | None,
    now: datetime,
    settings: PolicySettings,
    simulate_after_hours: bool = False,
) -> RiskAssessment:
    """依營運條件標示存取風險（可解釋規則，非異常偵測模型）。"""
    flags: list[str] = []
    messages: list[str] = []

    local = now.astimezone(TZ_TAIPEI)
    after_hours = simulate_after_hours or not (
        settings.business_hour_start <= local.hour < settings.business_hour_end
    )
    if after_hours:
        flags.append("after_hours")
        if simulate_after_hours:
            messages.append("Demo 開關：模擬非營業時間操作。")
        else:
            messages.append(
                f"目前為非營業時段（營業 {settings.business_hour_start:02d}:00–"
                f"{settings.business_hour_end:02d}:00 台北時間）。"
            )

    qty = abs(float(quantity)) if quantity is not None else 0.0
    if action in {"inventory.write", "reorder.approve", "reorder.request"} and qty >= settings.high_impact_qty:
        flags.append("high_impact")
        messages.append(
            f"高影響數量（|{qty:.0f}| ≥ 門檻 {settings.high_impact_qty} 件），核准後對庫存／採購影響較大。"
        )

    if (
        principal
        and store_id
        and principal.home_store_id
        and store_id != principal.home_store_id
        and action in STORE_SCOPED_ACTIONS
    ):
        flags.append("cross_store")
        messages.append(
            f"跨店操作：目標門市 {store_id} 不同於主店 {principal.home_store_id}。"
        )

    if "high_impact" in flags and ("cross_store" in flags or "after_hours" in flags):
        level = "high"
    elif flags:
        level = "medium"
    else:
        level = "low"
    return RiskAssessment(level=level, flags=tuple(flags), messages=tuple(messages))


def _needs_stepup(action: str, risk: RiskAssessment) -> bool:
    if action in ADMIN_ONLY_ACTIONS or action == "model.retrain":
        return True
    if action == "reorder.approve" and risk.is_elevated:
        return True
    if action == "inventory.write" and "high_impact" in risk.flags:
        return True
    return False


def decide(
    *,
    principal: Principal | None,
    action: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    store_id: str | None = None,
    quantity: float | None = None,
    request_id: str = "",
    correlation_id: str = "",
    now: datetime | None = None,
    settings: PolicySettings | None = None,
    simulate_after_hours: bool = False,
    payload_summary: str = "",
    before: dict | None = None,
    after: dict | None = None,
) -> AuthzDecision:
    """純函數 PDP：預設拒絕，通過所有檢查才允許。"""
    settings = settings or PolicySettings()
    now = now or datetime.now(TZ_TAIPEI)
    if now.tzinfo is None:
        now = now.replace(tzinfo=TZ_TAIPEI)

    risk = assess_access_risk(
        action=action,
        principal=principal,
        store_id=store_id,
        quantity=quantity,
        now=now,
        settings=settings,
        simulate_after_hours=simulate_after_hours,
    )

    def result(
        allowed: bool,
        outcome: str,
        code: str,
        reason: str,
        require_stepup: bool = False,
    ) -> AuthzDecision:
        return AuthzDecision(
            allowed=allowed,
            outcome=outcome,
            reason_code=code,
            reason=reason,
            action=action,
            principal=principal,
            resource_type=resource_type,
            resource_id=resource_id,
            store_id=store_id,
            request_id=request_id,
            correlation_id=correlation_id,
            risk=risk,
            require_stepup=require_stepup,
            quantity=quantity,
            payload_summary=payload_summary,
            before=before,
            after=after,
        )

    if principal is None:
        return result(False, "deny", REASON_UNAUTHENTICATED, "未登入，預設拒絕。")
    if not principal.is_active:
        return result(False, "deny", REASON_INACTIVE, "帳號已停用，預設拒絕。")
    if action not in ACTION_CATALOG:
        return result(
            False,
            "deny",
            REASON_UNKNOWN_ACTION,
            f"未知動作「{action}」，預設拒絕。",
        )
    if action in {"auth.login", "auth.logout", "auth.stepup"}:
        # 這些由認證流程自行稽核，不作為授權標的。
        return result(True, "allow", REASON_ALLOW, "認證事件。")

    if action not in principal.permissions:
        label = ACTION_CATALOG.get(action, action)
        return result(
            False,
            "deny",
            REASON_PERMISSION_DENIED,
            f"角色「{principal.role_label}」缺少權限 {action}（{label}），預設拒絕。",
        )

    if action in ADMIN_ONLY_ACTIONS and principal.role != "admin":
        return result(
            False,
            "deny",
            REASON_ADMIN_SESSION_REQUIRED,
            "此動作僅限管理者工作階段。",
        )

    if action in STORE_SCOPED_ACTIONS:
        if not store_id:
            return result(
                False,
                "deny",
                REASON_SCOPE_DENIED,
                "此動作需要明確的門市資源，未指定則預設拒絕。",
            )
        if not principal.in_store_scope(store_id):
            return result(
                False,
                "deny",
                REASON_SCOPE_DENIED,
                f"門市 {store_id} 不在你的資料範圍，跨店隔離生效。",
            )

    require_stepup = _needs_stepup(action, risk)
    if require_stepup:
        max_age = timedelta(minutes=max(1, int(settings.stepup_minutes)))
        if not principal.stepup_is_fresh(now, max_age):
            return result(
                False,
                "challenge",
                REASON_STEPUP_REQUIRED,
                f"敏感操作需要較高信任條件：請在 {settings.stepup_minutes} 分鐘內完成再驗證。",
                require_stepup=True,
            )

    return result(True, "allow", REASON_ALLOW, "通過權限、資料範圍與信任條件檢查。")
