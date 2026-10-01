"""当前操作人与归属权限的基础模型。

示例项目没有登录态，前端通过请求头表明当前角色和班组；后端仍以这里的结果作为
唯一写入口径，不能只靠前端隐藏按钮。
"""
from __future__ import annotations

from dataclasses import dataclass


class AccessDeniedError(Exception):
    """越权写入：HTTP 层统一转换为 403。"""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field
        self.message = message


class WorkflowError(Exception):
    """业务状态不允许继续：HTTP 层统一转换为 400。"""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field
        self.message = message


@dataclass(frozen=True)
class Operator:
    role: str
    team: str = ""

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_crew(self) -> bool:
        return self.role == "crew"

    def require_admin(self, field: str, action: str) -> None:
        if not self.is_admin:
            raise AccessDeniedError(field, f"越权提交：仅值班管理员可以{action}，当前班组「{self.team or '未指定'}」没有该资格")

    def require_crew(self, field: str, action: str) -> None:
        if self.is_admin:
            raise AccessDeniedError(field, f"越权提交：值班管理员只能跨班组核对，不能{action}")
        if not self.is_crew or not self.team:
            raise AccessDeniedError(field, f"越权提交：未选择责任班组，只能查看，不能{action}")
