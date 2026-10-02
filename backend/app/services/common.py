"""列表查询的共用写法：过滤、计数、切片、排序都从这里过，各模块不再各写一套。

- 每次查询基于同一份快照，并发增删不会把同一条记录切进两页；
- 分页参数在这里统一校验，页大小超上限直接报错并说明；
- 导出走全量清单，不受分页上限约束，也不再用写死的大页大小去截。
"""
from __future__ import annotations

from typing import Any

from app.pagination import paginate, parse_page_params, stable_order
from app.store import store


def list_module_entries(
    module: str,
    keyword_field: str,
    *,
    keyword: str | None,
    status: str | None,
    page: int,
    size: int,
) -> tuple[list[dict[str, Any]], int]:
    """先校验分页参数，再在同一份快照上过滤、计数、切片。"""
    params = parse_page_params(page, size)
    rows = store.snapshot(module)
    if keyword:
        rows = [row for row in rows if keyword in str(row.get(keyword_field, ""))]
    if status:
        rows = [row for row in rows if row.get("status") == status]
    return paginate(rows, params)


def list_all_entries(module: str) -> tuple[list[dict[str, Any]], int]:
    """导出用的全量清单：条数与明细来自同一份快照，顺序与分页口径一致。"""
    rows = stable_order(store.snapshot(module))
    return rows, len(rows)
