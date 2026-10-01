"""班组工作台接口。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.access import Operator
from app.dependencies import get_operator
from app.services.workbench import service

router = APIRouter(prefix="/api/workbench", tags=["班组工作台"])


@router.get("/todos")
def list_todos(
    include_done: bool = Query(default=False),
    operator: Operator = Depends(get_operator),
) -> dict[str, object]:
    """班组只看本班组待办；值班管理员可查看跨班组核对和归属调整待办。"""
    return service.todos(operator, include_done=include_done)
