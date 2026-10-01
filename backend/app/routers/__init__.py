"""业务模块路由汇总。

这里统一按别名导入再暴露 ROUTERS：模块名有可能和内置名撞车（某个业务模块就叫 dict、list
这种名字时），按名字直接 import 会把内置类型覆盖掉，函数注解在运行时求值就会报
'module' object is not subscriptable。
"""
from __future__ import annotations

from app.routers import pipe as router_pipe
from app.routers import manhole as router_manhole
from app.routers import workbench as router_workbench
from app.routers import valve as router_valve
from app.routers import pumpstation as router_pumpstation
from app.routers import patrol as router_patrol
from app.routers import defect as router_defect
from app.routers import cctv as router_cctv
from app.routers import repair as router_repair
from app.routers import pressure as router_pressure
from app.routers import flow as router_flow
from app.routers import leak as router_leak
from app.routers import dredge as router_dredge
from app.routers import material as router_material
from app.routers import equip as router_equip
from app.routers import traffic as router_traffic
from app.routers import complaint as router_complaint
from app.routers import fund as router_fund
from app.routers import archive as router_archive

ROUTERS = [router_pipe, router_manhole, router_workbench, router_valve, router_pumpstation, router_patrol, router_defect, router_cctv, router_repair, router_pressure, router_flow, router_leak, router_dredge, router_material, router_equip, router_traffic, router_complaint, router_fund, router_archive]
