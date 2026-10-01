"""班组工作台：各班组待办的归集、查询与办结。

检查井归属调整等动作会把结果回写成这里的待办；班组成员只看本班组，
值班管理员可以跨班组查看全部待办。
"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.errors import Forbidden
from app.identity import Identity
from app.store import store

MODULE = "workbench"
CLOSE_ACTION = "办结"


class WorkbenchService:
    def add_todo(self, *, team: str, kind: str, content: str, well_code: str = "") -> dict[str, Any]:
        """往指定班组的工作台写一条待办，归属调整回写就走这里。"""
        rows = store.rows(MODULE)
        todo: dict[str, Any] = {
            "id": max((int(row.get("id", 0)) for row in rows), default=0) + 1,
            "班组": team,
            "类型": kind,
            "内容": content,
            "关联井编号": well_code,
            "时间": date.today().isoformat(),
            "status": "待办",
            "pending": True,
            "abnormal": False,
        }
        rows.append(todo)
        return todo

    def list_todos(
        self,
        identity: Identity,
        *,
        team: str | None = None,
        page: int = 1,
        size: int = 50,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if identity.is_admin:
            if team:
                rows = [row for row in rows if row.get("班组") == team]
        else:
            rows = [row for row in rows if row.get("班组") == identity.team]
        rows = sorted(rows, key=lambda row: (not row.get("pending"), -int(row.get("id", 0))))
        total = len(rows)
        start = max(page - 1, 0) * size
        return [self._decorate(identity, row) for row in rows[start:start + size]], total

    @staticmethod
    def _decorate(identity: Identity, row: dict[str, Any]) -> dict[str, Any]:
        item = dict(row)
        item["可办结"] = identity.is_admin or bool(identity.team) and identity.team == row.get("班组")
        return item

    def run_action(self, identity: Identity, todo_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        todo = store.find(MODULE, todo_id)
        if todo is None:
            return None, f"待办 {todo_id} 不存在或已清理"
        if action != CLOSE_ACTION:
            return None, f"动作「{action}」不属于班组工作台可执行范围"
        owner = str(todo.get("班组") or "")
        if not identity.is_admin and identity.team != owner:
            raise Forbidden(f"动作「办结」不允许：该待办归「{owner}」处理，当前身份「{identity.label}」仅可查看")
        todo["status"] = "已办结"
        todo["pending"] = False
        return todo, f"待办 {todo_id} 已办结"
