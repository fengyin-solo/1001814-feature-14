"""班组工作台：按当前班组或值班管理员汇总待办。"""
from __future__ import annotations

from typing import Any

from app.access import Operator
from app.store import store

TODO_MODULE = "manhole_todos"


class WorkbenchService:
    def todos(self, operator: Operator, *, include_done: bool = False) -> dict[str, Any]:
        rows = store.rows(TODO_MODULE)
        if operator.is_crew:
            rows = [row for row in rows if row.get("team") == operator.team]
        if not include_done:
            rows = [row for row in rows if row.get("status") == "待处理"]
        rows = sorted(rows, key=lambda row: int(row.get("id", 0)), reverse=True)
        pending_cleaning = sum(1 for row in rows if row.get("type") == "cleaning_confirmation" and row.get("status") == "待处理")
        ownership_changes = sum(1 for row in rows if row.get("type") == "ownership_transfer" and row.get("status") == "待处理")
        return {
            "role": "admin" if operator.is_admin else "crew",
            "team": operator.team,
            "items": [dict(row) for row in rows],
            "total": len(rows),
            "pending_cleaning": pending_cleaning,
            "ownership_changes": ownership_changes,
        }


service = WorkbenchService()
