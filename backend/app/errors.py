"""共享异常：越权提交统一用 Forbidden，消息里写清是哪一项不被允许、为什么。"""
from __future__ import annotations


class Forbidden(Exception):
    """越权提交：路由层转成 403，detail 直接给操作者看。"""
