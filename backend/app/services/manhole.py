"""检查井业务规则：归属约束、清掏历史与班组待办。"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.access import AccessDeniedError, Operator, WorkflowError
from app.store import store

MODULE = "manhole"
CLEANING_MODULE = "manhole_cleanings"
TODO_MODULE = "manhole_todos"
REQUIRED_FIELDS = ["井编号", "所在道路", "井盖类别"]
TEAMS = ["排水一班", "排水二班", "排水三班"]
CREW_STATUSES = ["待清掏", "正常使用", "井盖缺失", "已废弃"]


class ManholeService:
    def teams(self) -> list[str]:
        return TEAMS.copy()

    def list_entries(
        self,
        operator: Operator,
        *,
        keyword: str | None = None,
        status: str | None = None,
        scope: str = "mine",
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if operator.is_crew and scope != "all":
            rows = [row for row in rows if row.get("责任班组") == operator.team]
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("井编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return [self._decorate(row, operator) for row in rows[start:start + size]], total

    def get_entry(self, entry_id: int, operator: Operator) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None
        return self._decorate(entry, operator)

    def list_cleanings(self, entry_id: int) -> list[dict[str, Any]] | None:
        if store.find(MODULE, entry_id) is None:
            return None
        return sorted(
            [dict(row) for row in store.rows(CLEANING_MODULE) if row.get("manhole_id") == entry_id],
            key=lambda row: (-int(row.get("id", 0)),),
        )

    def create_entry(self, values: dict[str, Any], operator: Operator) -> tuple[dict[str, Any] | None, list[str]]:
        operator.require_crew("责任班组", "登记检查井")
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        team = str(values.get("责任班组") or operator.team).strip()
        if team != operator.team:
            raise AccessDeniedError("责任班组", f"越权提交：第「责任班组」项不允许登记为「{team}」，本班组只能登记归属「{operator.team}」的检查井")
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": store.next_id(MODULE)}
        entry.update({field: values.get(field) for field in ["井编号", "所在道路", "井盖类别", "井室深度", "井室尺寸"]})
        entry["上次清掏日"] = "—"
        entry["责任班组"] = team
        entry["status"] = CREW_STATUSES[0]
        entry["检查井状态"] = CREW_STATUSES[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        self._add_todo(
            team,
            entry["id"],
            "cleaning_confirmation",
            f"新井 {entry['井编号']} 已登记，请安排并确认清掏结果",
        )
        return self._decorate(entry, operator), []

    def register_cleaning(self, entry_id: int, values: dict[str, Any], operator: Operator) -> dict[str, Any]:
        operator.require_crew("清掏结果", "登记清掏结果")
        entry = self._require_entry(entry_id)
        self._require_owner(entry, operator.team, "登记清掏结果")
        cleaned_on = str(values.get("cleaned_on") or date.today().isoformat()).strip()
        result = str(values.get("result") or "").strip()
        if not result:
            raise WorkflowError("清掏结果", "清掏结果不能为空，请填写本次清掏情况")
        pending = self._latest_pending(entry_id)
        if pending is not None:
            raise WorkflowError("清掏结果", f"已有 {pending.get('cleaned_on')} 的清掏结果待确认，不能重复登记")

        record = {
            "id": store.next_id(CLEANING_MODULE),
            "manhole_id": entry_id,
            "status": "待确认",
            "cleaned_on": cleaned_on,
            "result": result,
            "operator_team": operator.team,
            "owner_team": entry.get("责任班组"),
        }
        store.rows(CLEANING_MODULE).append(record)
        entry["上次清掏日"] = cleaned_on
        entry["检查井状态"] = "待清掏"
        entry["status"] = "待清掏"
        entry["pending"] = True
        self._close_todos(entry_id, "cleaning_confirmation")
        self._add_todo(
            operator.team,
            entry_id,
            "cleaning_confirmation",
            f"确认 {entry.get('井编号')} 本次清掏结果",
            payload={"cleaning_id": record["id"]},
        )
        return self._decorate(entry, operator)

    def confirm_cleaning(self, entry_id: int, values: dict[str, Any], operator: Operator) -> dict[str, Any]:
        operator.require_crew("确认清掏结果", "确认清掏结果")
        entry = self._require_entry(entry_id)
        record = self._require_cleaning(entry_id, values)
        if record.get("operator_team") != operator.team:
            raise AccessDeniedError(
                "确认清掏结果",
                f"越权提交：第「确认清掏结果」项不允许操作 {record.get('cleaned_on')} 的清掏记录，该记录归属班组为「{record.get('operator_team')}」，当前班组「{operator.team}」只能查看",
            )
        if entry.get("责任班组") != operator.team:
            raise AccessDeniedError("责任班组", f"越权提交：第「责任班组」项显示该井由「{entry.get('责任班组')}」维护，当前班组「{operator.team}」只能查看")
        if record.get("status") != "待确认":
            raise WorkflowError("确认清掏结果", f"该清掏记录已{record.get('status')}，不能重复确认")
        record["status"] = "已确认"
        entry["status"] = "正常使用"
        entry["检查井状态"] = "正常使用"
        entry["pending"] = False
        entry["abnormal"] = False
        self._close_todos(entry_id, "cleaning_confirmation")
        return self._decorate(entry, operator)

    def verify_cleaning(self, entry_id: int, values: dict[str, Any], operator: Operator) -> dict[str, Any]:
        operator.require_admin("核对清掏结果", "跨班组核对")
        entry = self._require_entry(entry_id)
        record = self._require_cleaning(entry_id, values)
        if record.get("status") != "已确认":
            raise WorkflowError("核对清掏结果", "清掏结果需先由责任班组确认，值班管理员才能跨班组核对")
        record["status"] = "已核对"
        verified_at = str(values.get("verified_at") or date.today().isoformat())
        record["verified_by"] = "值班管理员"
        record["verified_at"] = verified_at
        entry["status"] = "正常使用"
        entry["检查井状态"] = "正常使用"
        entry["pending"] = False
        entry["abnormal"] = False
        self._close_todos(entry_id, "cleaning_confirmation")
        return self._decorate(entry, operator)

    def change_owner(self, entry_id: int, values: dict[str, Any], operator: Operator) -> dict[str, Any]:
        operator.require_admin("责任班组", "调整归属班组")
        entry = self._require_entry(entry_id)
        target_team = str(values.get("team") or values.get("责任班组") or "").strip()
        if target_team not in TEAMS:
            raise WorkflowError("责任班组", f"目标责任班组「{target_team}」不存在")
        old_team = str(entry.get("责任班组") or "")
        if target_team == old_team:
            raise WorkflowError("责任班组", "检查井已归属该班组，无需调整")
        pending = self._latest_pending(entry_id)
        if pending is not None:
            raise WorkflowError("责任班组", f"{pending.get('cleaned_on')} 的清掏结果仍待确认，请先完成清掏确认再调整归属")

        entry["责任班组"] = target_team
        self._close_todos(entry_id, "ownership_transfer")
        self._add_todo(
            target_team,
            entry_id,
            "ownership_transfer",
            f"{entry.get('井编号')} 已由 {old_team} 调整至 {target_team}",
            payload={"from_team": old_team, "to_team": target_team},
        )
        return self._decorate(entry, operator)

    def _require_entry(self, entry_id: int) -> dict[str, Any]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            raise WorkflowError("检查井", f"检查井 {entry_id} 不存在或已归档")
        return entry

    def _require_owner(self, entry: dict[str, Any], team: str, action: str) -> None:
        owner = str(entry.get("责任班组") or "")
        if owner != team:
            raise AccessDeniedError("责任班组", f"越权提交：第「责任班组」项不允许{action}；检查井 {entry.get('井编号')} 归属「{owner}」，当前班组「{team}」只能查看")

    def _require_cleaning(self, entry_id: int, values: dict[str, Any]) -> dict[str, Any]:
        cleaning_id = values.get("cleaning_id")
        if cleaning_id is None:
            record = self._latest_record(entry_id)
        else:
            record = store.find(CLEANING_MODULE, int(cleaning_id))
            if record is not None and record.get("manhole_id") != entry_id:
                record = None
        if record is None:
            raise WorkflowError("清掏结果", "没有可操作的清掏记录")
        return record

    def _latest_record(self, entry_id: int) -> dict[str, Any] | None:
        records = [row for row in store.rows(CLEANING_MODULE) if row.get("manhole_id") == entry_id]
        return max(records, key=lambda row: int(row.get("id", 0)), default=None)

    def _latest_pending(self, entry_id: int) -> dict[str, Any] | None:
        records = [
            row for row in store.rows(CLEANING_MODULE)
            if row.get("manhole_id") == entry_id and row.get("status") == "待确认"
        ]
        return max(records, key=lambda row: int(row.get("id", 0)), default=None)

    def _latest_snapshot(self, entry_id: int) -> dict[str, Any]:
        record = self._latest_record(entry_id)
        if record is None:
            return {
                "最近清掏日": "—",
                "最近清掏情况": "暂无清掏记录",
                "清掏确认状态": "未登记",
                "历史归属班组": "",
            }
        return {
            "最近清掏日": record.get("cleaned_on"),
            "最近清掏情况": record.get("result"),
            "清掏确认状态": record.get("status"),
            "历史归属班组": record.get("operator_team"),
        }

    def _decorate(self, entry: dict[str, Any], operator: Operator) -> dict[str, Any]:
        result = dict(entry)
        result.update(self._latest_snapshot(int(entry.get("id", 0))))
        owner = str(entry.get("责任班组") or "")
        record = self._latest_record(int(entry.get("id", 0)))
        is_owner = operator.is_crew and owner == operator.team
        result["当前角色"] = "值班管理员" if operator.is_admin else "班组人员"
        result["当前班组"] = operator.team
        result["权限"] = {
            "can_view": True,
            "can_register_cleaning": is_owner,
            "can_confirm_cleaning": is_owner and record is not None
            and record.get("operator_team") == operator.team
            and record.get("status") == "待确认",
            "can_verify_cleaning": operator.is_admin and record is not None and record.get("status") == "已确认",
            "can_change_owner": operator.is_admin,
            "can_create_manhole": operator.is_crew,
        }
        return result

    def _add_todo(
        self,
        team: str,
        entry_id: int,
        todo_type: str,
        title: str,
        *,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        todo = {
            "id": store.next_id(TODO_MODULE),
            "module": MODULE,
            "entry_id": entry_id,
            "type": todo_type,
            "team": team,
            "title": title,
            "status": "待处理",
            "payload": payload or {},
            "created_at": date.today().isoformat(),
        }
        store.rows(TODO_MODULE).append(todo)
        return todo

    def _close_todos(self, entry_id: int, todo_type: str) -> None:
        for todo in store.rows(TODO_MODULE):
            if (
                todo.get("module") == MODULE
                and todo.get("entry_id") == entry_id
                and todo.get("type") == todo_type
                and todo.get("status") == "待处理"
            ):
                todo["status"] = "已处理"


service = ManholeService()
