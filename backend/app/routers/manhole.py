"""检查井接口：维护归属、清掏登记/确认和值班管理员核对。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.access import AccessDeniedError, Operator, WorkflowError
from app.dependencies import get_operator
from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.manhole import ManholeService

router = APIRouter(prefix="/api/manhole", tags=["检查井"])

service = ManholeService()

LIST_FIELDS = ["井编号", "所在道路", "井盖类别", "井室深度", "井室尺寸", "上次清掏日", "责任班组", "检查井状态"]
STATUSES = ["待清掏", "正常使用", "井盖缺失", "已废弃"]


def _denied(error: AccessDeniedError) -> HTTPException:
    return HTTPException(status_code=403, detail={"field": error.field, "message": error.message})


def _workflow_error(error: WorkflowError) -> HTTPException:
    return HTTPException(status_code=400, detail={"field": error.field, "message": error.message})


@router.get("/teams")
def list_teams() -> dict[str, list[str]]:
    return {"items": service.teams()}


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按井编号检索"),
    status: str | None = Query(default=None, description="待清掏、正常使用、井盖缺失、已废弃"),
    scope: str = Query(default="mine", description="mine 只看本班组；all 跨班组查看"),
    page: int = 1,
    size: int = 20,
    operator: Operator = Depends(get_operator),
) -> PageResult[dict]:
    """按归属口径过滤检查井；跨班组列表仍返回归属和最近一次清掏信息。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(operator, keyword=keyword, status=status, scope=scope, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/export")
def export_entries(operator: Operator = Depends(get_operator)) -> dict[str, Any]:
    """导出检查井清单：返回当前操作人可见范围下的全量数据。"""
    items, total = service.list_entries(operator, scope="all", page=1, size=10000)
    return {"module": "manhole", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int, operator: Operator = Depends(get_operator)) -> dict:
    """读取单条检查井明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id, operator)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"检查井 {entry_id} 不存在或已归档")
    return entry


@router.get("/{entry_id}/cleanings")
def list_cleanings(entry_id: int) -> dict[str, Any]:
    """返回清掏历史；记录里保留作业时班组，班组调整后不随当前归属改写。"""
    items = service.list_cleanings(entry_id)
    if items is None:
        raise HTTPException(status_code=404, detail=f"检查井 {entry_id} 不存在或已归档")
    return {"items": items, "total": len(items)}


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload, operator: Operator = Depends(get_operator)) -> ActionResult:
    """登记一条检查井；班组只能登记归属本班组的井。"""
    try:
        entry, missing = service.create_entry(payload.values, operator)
    except AccessDeniedError as error:
        raise _denied(error) from error
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="检查井已登记", entry=entry)


@router.post("/{entry_id}/cleanings", response_model=ActionResult)
def register_cleaning(entry_id: int, payload: EntryPayload, operator: Operator = Depends(get_operator)) -> ActionResult:
    """责任班组登记本次清掏结果。"""
    try:
        entry = service.register_cleaning(entry_id, payload.values, operator)
    except AccessDeniedError as error:
        raise _denied(error) from error
    except WorkflowError as error:
        raise _workflow_error(error) from error
    return ActionResult(ok=True, message="清掏结果已登记，等待本班组确认", entry=entry)


@router.post("/{entry_id}/cleanings/confirm", response_model=ActionResult)
def confirm_cleaning(entry_id: int, payload: EntryPayload, operator: Operator = Depends(get_operator)) -> ActionResult:
    """只有历史记录中的作业班组可以确认自己的清掏结果。"""
    try:
        entry = service.confirm_cleaning(entry_id, payload.values, operator)
    except AccessDeniedError as error:
        raise _denied(error) from error
    except WorkflowError as error:
        raise _workflow_error(error) from error
    return ActionResult(ok=True, message="清掏结果已确认", entry=entry)


@router.post("/{entry_id}/cleanings/verify", response_model=ActionResult)
def verify_cleaning(entry_id: int, payload: EntryPayload, operator: Operator = Depends(get_operator)) -> ActionResult:
    """值班管理员跨班组核对，不因此获得清掏登记或确认资格。"""
    try:
        entry = service.verify_cleaning(entry_id, payload.values, operator)
    except AccessDeniedError as error:
        raise _denied(error) from error
    except WorkflowError as error:
        raise _workflow_error(error) from error
    return ActionResult(ok=True, message="清掏结果已由值班管理员核对", entry=entry)


@router.post("/{entry_id}/ownership", response_model=ActionResult)
def change_owner(entry_id: int, payload: EntryPayload, operator: Operator = Depends(get_operator)) -> ActionResult:
    """值班管理员调整归属，并向新班组工作台回写待办。"""
    try:
        entry = service.change_owner(entry_id, payload.values, operator)
    except AccessDeniedError as error:
        raise _denied(error) from error
    except WorkflowError as error:
        raise _workflow_error(error) from error
    return ActionResult(ok=True, message="归属班组已调整，待办已回写至新班组工作台", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload, operator: Operator = Depends(get_operator)) -> ActionResult:
    """兼容统一动作入口，并按同一套归属规则鉴权。"""
    action = str(payload.values.get("action") or "").strip()
    try:
        if action in {"登记清掏结果", "安排清掏"}:
            entry = service.register_cleaning(entry_id, payload.values, operator)
            message = "清掏结果已登记，等待本班组确认"
        elif action in {"确认清掏结果", "确认正常"}:
            entry = service.confirm_cleaning(entry_id, payload.values, operator)
            message = "清掏结果已确认"
        elif action == "核对清掏结果":
            entry = service.verify_cleaning(entry_id, payload.values, operator)
            message = "清掏结果已由值班管理员核对"
        elif action == "调整归属":
            entry = service.change_owner(entry_id, payload.values, operator)
            message = "归属班组已调整，待办已回写至新班组工作台"
        else:
            return ActionResult(ok=False, message=f"动作「{action}」不属于检查井归属流程可执行范围")
    except AccessDeniedError as error:
        raise _denied(error) from error
    except WorkflowError as error:
        raise _workflow_error(error) from error
    return ActionResult(ok=True, message=message, entry=entry)
