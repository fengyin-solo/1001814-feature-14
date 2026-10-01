"""操作身份：从请求头解析当前值班的角色与班组，供归属校验使用。

前端在切换身份时把角色、班组写进请求头；直接调接口没带请求头时按值班管理员处理，
保证克隆下来就能跑通。
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import unquote

from fastapi import Request

ROLE_ADMIN = "admin"  # 值班管理员
ROLE_CREW = "crew"  # 班组成员

TEAMS = ["清掏一班", "清掏二班", "清掏三班"]

_ROLE_LABELS = {ROLE_ADMIN: "值班管理员", ROLE_CREW: "班组成员"}


@dataclass(frozen=True)
class Identity:
    role: str = ROLE_ADMIN
    team: str = ""

    @property
    def is_admin(self) -> bool:
        return self.role == ROLE_ADMIN

    @property
    def label(self) -> str:
        if self.is_admin:
            return "值班管理员"
        return f"{self.team}·班组成员" if self.team else "班组成员（未识别班组）"


def get_identity(request: Request) -> Identity:
    """从请求头读出操作身份；缺头时按值班管理员处理。

    班组名是中文，直接放请求头会被按 latin-1 解码成乱码，
    前端先做了百分号编码，这里解码还原。
    """
    role = (request.headers.get("x-operator-role") or ROLE_ADMIN).strip().lower()
    team = unquote(request.headers.get("x-operator-team") or "").strip()
    if role not in _ROLE_LABELS:
        role = ROLE_ADMIN
    if role == ROLE_ADMIN:
        team = ""
    return Identity(role=role, team=team)
