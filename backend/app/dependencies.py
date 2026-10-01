"""FastAPI 请求依赖。"""
from __future__ import annotations

from fastapi import Header

from app.access import Operator


def get_operator(
    x_operator_role: str | None = Header(default=None, alias="X-Operator-Role"),
    x_operator_team: str | None = Header(default=None, alias="X-Operator-Team"),
) -> Operator:
    role = (x_operator_role or "viewer").strip()
    team = (x_operator_team or "").strip()
    if role not in {"crew", "admin"}:
        role = "viewer"
    return Operator(role=role, team=team)
