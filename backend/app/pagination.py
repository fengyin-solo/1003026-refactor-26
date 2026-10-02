"""分页与总数的统一口径：全平台列表接口共用这一份实现。

约定：
- 总数按过滤后的全量记录数计算，与页码、页大小无关；
- 记录先按 id 稳定排序再切片，切片只切一次，同一批数据翻两遍不重复、不遗漏；
- 页大小有上限（settings.page_size_max），超了报错并说明原因，不静默截断；
- 参数不合法抛 PageParamsError，由接口层统一翻译成 400。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.config import settings


class PageParamsError(ValueError):
    """分页参数不合法；消息里写清原因，由接口层转成 400 返回。"""


@dataclass(frozen=True)
class PageParams:
    page: int
    size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


def parse_page_params(page: int, size: int) -> PageParams:
    """校验页码与页大小；不合法直接报错说明，不静默改参数。"""
    if page < 1:
        raise PageParamsError(f"页码从 1 开始，收到的是 {page}")
    if size < 1:
        raise PageParamsError(f"每页条数至少为 1，收到的是 {size}")
    if size > settings.page_size_max:
        raise PageParamsError(
            f"每页最多 {settings.page_size_max} 条，收到的是 {size}，请缩小分页范围"
        )
    return PageParams(page=page, size=size)


def stable_order(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按 id 升序给出确定顺序：id 唯一，同一批数据翻多少遍顺序都一样。"""
    return sorted(rows, key=lambda row: int(row.get("id", 0)))


def paginate(rows: list[dict[str, Any]], params: PageParams) -> tuple[list[dict[str, Any]], int]:
    """对过滤后的全量记录先数总数、再切一页；全平台只在这里切这一次。"""
    total = len(rows)
    ordered = stable_order(rows)
    return ordered[params.offset:params.offset + params.size], total
