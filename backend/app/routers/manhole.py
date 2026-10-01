"""检查井接口：维护检查井，覆盖安排清掏、确认清掏、跨班组核对、归属调整等动作。

归属约束在服务层收口：越权提交会抛 Forbidden，这里统一转成 403，
detail 里写清是哪一项不被允许，前端原样展示给操作者。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from app.errors import Forbidden
from app.identity import get_identity
from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.manhole import ManholeService

router = APIRouter(prefix="/api/manhole", tags=["检查井"])

service = ManholeService()

LIST_FIELDS = ["井编号", "所在道路", "井盖类别", "井室深度", "井室尺寸", "上次清掏日", "责任班组", "检查井状态"]
STATUSES = ["待清掏", "正常使用", "井盖缺失", "已废弃"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    request: Request,
    keyword: str | None = Query(default=None, description="按井编号检索"),
    status: str | None = Query(default=None, description="待清掏、正常使用、井盖缺失、已废弃"),
    road: str | None = Query(default=None, description="按所在道路检索"),
    cover: str | None = Query(default=None, description="按井盖类别检索"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按井编号与状态过滤检查井列表；每行带归属班组、最近清掏与当前身份可执行的动作。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    identity = get_identity(request)
    items, total = service.list_entries(identity, keyword=keyword, status=status, road=road, cover=cover, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/export")
def export_entries(request: Request) -> dict[str, Any]:
    """导出检查井清单：返回当前身份可见的全量数据。"""
    identity = get_identity(request)
    items, total = service.list_entries(identity, page=1, size=10000)
    return {"module": "manhole", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int, request: Request) -> dict:
    """读取单条检查井明细：含清掏记录与归属调整记录；不存在时给出可读的错误说明。"""
    identity = get_identity(request)
    entry = service.get_entry(identity, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"检查井 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload, request: Request) -> ActionResult:
    """登记一条检查井：只能登记到本班组；越权提交被拦下并说明是哪一项不允许。"""
    identity = get_identity(request)
    try:
        entry, missing = service.create_entry(identity, payload.values)
    except Forbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="检查井已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload, request: Request) -> ActionResult:
    """对单条检查井执行动作；越权提交被拦下（403），不允许的动作会说明原因。"""
    identity = get_identity(request)
    action = str(payload.values.get("action") or "").strip()
    try:
        entry, message = service.run_action(identity, entry_id, action, payload.values)
    except Forbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
