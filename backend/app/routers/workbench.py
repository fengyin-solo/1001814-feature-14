"""班组工作台接口：按身份返回本班组待办，检查井归属调整的回写在这里看得到。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from app.errors import Forbidden
from app.identity import get_identity
from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.workbench import WorkbenchService

router = APIRouter(prefix="/api/workbench", tags=["班组工作台"])

service = WorkbenchService()


@router.get("/todos", response_model=PageResult[dict])
def list_todos(
    request: Request,
    team: str | None = Query(default=None, description="值班管理员可按班组过滤"),
    page: int = 1,
    size: int = 50,
) -> PageResult[dict]:
    """列出待办：班组成员只看本班组，值班管理员可看全部或按班组过滤。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    identity = get_identity(request)
    items, total = service.list_todos(identity, team=team, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.post("/todos/{todo_id}/actions", response_model=ActionResult)
def run_action(todo_id: int, payload: EntryPayload, request: Request) -> ActionResult:
    """办结待办：只有归属班组或值班管理员能办结，越权提交会被拦下（403）。"""
    identity = get_identity(request)
    action = str(payload.values.get("action") or "").strip()
    try:
        todo, message = service.run_action(identity, todo_id, action)
    except Forbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if todo is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=todo)
