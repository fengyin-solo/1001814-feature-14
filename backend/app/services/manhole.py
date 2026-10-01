"""检查井业务规则：归属班组、状态流转、字段校验与筛选口径都收在这里。

归属约束：
- 检查井由「责任班组」维护，本班组可登记、安排清掏、确认清掏结果；
- 其他班组只读，提交写动作会被挡回（403），并指出是哪一项不允许；
- 值班管理员不替班组动手，只做跨班组核对与归属调整；
- 归属调整后历史清掏记录仍署名原班组，改动资格只跟当前责任班组走；
- 归属调整的结果会回写到双方班组的工作台待办。
"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.errors import Forbidden
from app.identity import TEAMS, Identity
from app.services.workbench import WorkbenchService
from app.store import store

MODULE = "manhole"
REQUIRED_FIELDS = ["井编号", "所在道路", "井盖类别"]
STATUS_ORDER = ["待清掏", "正常使用", "井盖缺失", "已废弃"]
FINAL_STATUS = STATUS_ORDER[-1]

# 班组动作：只有当前责任班组能执行
CREW_ACTION_RULES = {"安排清掏": "待清掏", "确认清掏": "正常使用", "确认正常": "正常使用", "废弃井室": "已废弃"}
# 值班管理员动作：跨班组核对、归属调整
ADMIN_ACTIONS = ["跨班组核对", "归属调整"]

workbench = WorkbenchService()


def _today() -> str:
    return date.today().isoformat()


def _well_code(entry: dict[str, Any]) -> str:
    return str(entry.get("井编号") or f"#{entry.get('id')}")


def _latest_dredge_text(entry: dict[str, Any]) -> str:
    records = entry.get("清掏记录") or []
    if not records:
        return "暂无清掏记录"
    latest = records[-1]
    return f"{latest.get('日期')} {latest.get('班组')}：{latest.get('结果')}"


class ManholeService:
    # ---- 查询：所有身份都能看，跨班组只读 ----
    @staticmethod
    def _allowed_actions(identity: Identity, entry: dict[str, Any]) -> list[str]:
        if identity.is_admin:
            return list(ADMIN_ACTIONS)
        if identity.team and identity.team == entry.get("责任班组"):
            return list(CREW_ACTION_RULES)
        return []

    def _decorate(self, identity: Identity, entry: dict[str, Any]) -> dict[str, Any]:
        row = dict(entry)
        owner = str(entry.get("责任班组") or "").strip() or "未指派"
        actions = self._allowed_actions(identity, entry)
        row["归属班组"] = owner
        row["最近清掏"] = _latest_dredge_text(entry)
        row["可执行动作"] = actions
        row["只读原因"] = "" if actions else f"归「{owner}」维护，当前身份「{identity.label}」仅可查看"
        return row

    def list_entries(
        self,
        identity: Identity,
        *,
        keyword: str | None = None,
        status: str | None = None,
        road: str | None = None,
        cover: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("井编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if road:
            rows = [row for row in rows if road in str(row.get("所在道路", ""))]
        if cover:
            rows = [row for row in rows if cover in str(row.get("井盖类别", ""))]
        total = len(rows)
        start = max(page - 1, 0) * size
        return [self._decorate(identity, row) for row in rows[start:start + size]], total

    def get_entry(self, identity: Identity, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        return None if entry is None else self._decorate(identity, entry)

    # ---- 登记：只有班组能登记，且只能登记到本班组 ----
    def create_entry(self, identity: Identity, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        if identity.is_admin:
            raise Forbidden("「登记检查井」不允许由值班管理员提交：请由责任班组登记，管理员可跨班组核对")
        if not identity.team:
            raise Forbidden("「登记检查井」不允许：当前身份未识别所属班组")
        owner = str(values.get("责任班组") or "").strip()
        if owner and owner != identity.team:
            raise Forbidden(f"字段「责任班组」不允许登记为「{owner}」：{identity.team} 只能登记归属本班组的检查井")
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        for field in ("井室深度", "井室尺寸"):
            if str(values.get(field) or "").strip():
                entry[field] = values.get(field)
        entry["责任班组"] = identity.team
        entry["上次清掏日"] = ""
        entry["检查井状态"] = STATUS_ORDER[0]
        entry["清掏记录"] = []
        entry["归属调整记录"] = []
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    # ---- 动作：按角色分流，越权一律挡回 ----
    def run_action(
        self,
        identity: Identity,
        entry_id: int,
        action: str,
        values: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"检查井 {entry_id} 不存在或已归档"
        if action in CREW_ACTION_RULES:
            self._require_owner_team(identity, entry, action)
            return self._run_crew_action(identity, entry, action, values)
        if action in ADMIN_ACTIONS:
            self._require_admin(identity, action)
            if action == "跨班组核对":
                return self._review(identity, entry, values)
            return self._reassign(identity, entry, values)
        return None, f"动作「{action}」不属于检查井可执行范围"

    @staticmethod
    def _require_owner_team(identity: Identity, entry: dict[str, Any], action: str) -> None:
        owner = str(entry.get("责任班组") or "").strip() or "未指派"
        code = _well_code(entry)
        if identity.is_admin:
            raise Forbidden(f"动作「{action}」不允许由值班管理员提交：检查井 {code} 归「{owner}」维护，管理员请使用「跨班组核对」")
        if identity.team != owner:
            raise Forbidden(f"动作「{action}」不允许：检查井 {code} 归「{owner}」维护，当前身份「{identity.label}」仅可查看")

    @staticmethod
    def _require_admin(identity: Identity, action: str) -> None:
        if not identity.is_admin:
            raise Forbidden(f"动作「{action}」不允许：仅值班管理员可执行，当前身份「{identity.label}」")

    @staticmethod
    def _run_crew_action(
        identity: Identity,
        entry: dict[str, Any],
        action: str,
        values: dict[str, Any],
    ) -> tuple[dict[str, Any], str]:
        if action == "确认清掏":
            result = str(values.get("清掏结果") or "").strip() or "清掏完成"
            record = {"日期": _today(), "班组": identity.team, "结果": result, "记录人": identity.label}
            entry.setdefault("清掏记录", []).append(record)
            entry["上次清掏日"] = record["日期"]
        target = CREW_ACTION_RULES[action]
        entry["status"] = target
        entry["检查井状态"] = target
        entry["pending"] = target != FINAL_STATUS
        entry["abnormal"] = False
        return entry, f"检查井 {_well_code(entry)} 已{action}"

    @staticmethod
    def _review(identity: Identity, entry: dict[str, Any], values: dict[str, Any]) -> tuple[dict[str, Any], str]:
        conclusion = str(values.get("核对结论") or "").strip() or "账实相符"
        entry.setdefault("核对记录", []).append({"日期": _today(), "核对结论": conclusion, "操作人": identity.label})
        entry["abnormal"] = False
        return entry, f"检查井 {_well_code(entry)} 已完成跨班组核对：{conclusion}"

    @staticmethod
    def _reassign(identity: Identity, entry: dict[str, Any], values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        code = _well_code(entry)
        new_team = str(values.get("新班组") or "").strip()
        if not new_team:
            return None, "归属调整缺少「新班组」，请指明接手班组"
        if new_team not in TEAMS:
            return None, f"班组「{new_team}」不在班组名录（{'、'.join(TEAMS)}）里"
        old_team = str(entry.get("责任班组") or "").strip() or "未指派"
        if new_team == old_team:
            return None, f"检查井 {code} 已归「{old_team}」维护，无需调整"
        entry["责任班组"] = new_team
        # 历史清掏记录保持原班组署名，不回改；改动资格只跟新的责任班组走
        entry.setdefault("归属调整记录", []).append(
            {"日期": _today(), "原班组": old_team, "新班组": new_team, "操作人": identity.label}
        )
        workbench.add_todo(
            team=new_team,
            kind="归属调整",
            well_code=code,
            content=f"接手检查井 {code}（原责任班组：{old_team}），请核对井室情况并安排清掏",
        )
        if old_team in TEAMS:
            workbench.add_todo(
                team=old_team,
                kind="归属调整",
                well_code=code,
                content=f"检查井 {code} 已移交「{new_team}」，历史清掏记录仍归本班组",
            )
        return entry, f"检查井 {code} 归属已由「{old_team}」调整为「{new_team}」，待办已回写双方班组工作台"
