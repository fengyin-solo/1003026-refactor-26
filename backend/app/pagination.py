"""列表分页的共用口径：所有模块的列表分页都收拢到这一份实现。

约定：
- 总数按过滤后的全量算，不是当前页的条数；
- 记录按 id 升序固定次序，全量里只切一次片；
- 页码从 1 开始，页大小有上限（settings.page_size_max），越界抛 PageParamsError 并写清原因；
- 翻页期间有人删记录时，按过滤条件缓存的有序 id 快照保证同一条记录不会出现在两页里：
  被删的记录直接从它所在的页消失，不会让后面的记录错位补上；
- 分页口径调整时递增 PAGING_SPEC_VERSION，缓存里的旧口径分页结果随之作废、按新口径重算。
"""
from __future__ import annotations

import threading
import time
from typing import Any, Hashable

from app.config import settings

# 分页口径版本：口径一变就递增，已缓存的分页结果自动作废、按新口径重算。
PAGING_SPEC_VERSION = 2

# 快照保留时长（秒）：超时后重新取数，避免过滤条件组合无限堆积占内存。
SNAPSHOT_TTL_SECONDS = 300.0


class PageParamsError(ValueError):
    """分页参数越界。消息面向操作员，由应用层原样转成 400 响应。"""


def check_page_params(page: int, size: int) -> None:
    """页码从 1 开始；页大小 1..page_size_max，超了报错并说明上限。"""
    if page < 1:
        raise PageParamsError(f"页码从 1 开始，收到 page={page}，请调整后再查询")
    if size < 1:
        raise PageParamsError(f"每页条数至少为 1，收到 size={size}，请调整后再查询")
    if size > settings.page_size_max:
        raise PageParamsError(
            f"每页最多 {settings.page_size_max} 条，收到 size={size}；"
            "请缩小每页条数翻页查看，或改用导出接口取全量"
        )


def _row_id(row: dict[str, Any]) -> int:
    return int(row.get("id", 0))


class PageSnapshots:
    """按过滤条件缓存有序 id 快照，让翻页期间的并发删除不会造成记录跨页重复。

    快照键里带分页口径版本：口径调整后旧快照自然失效，下次查询按新口径重算；
    快照有 TTL，超时自动重建，避免无限占用内存。
    """

    def __init__(self, ttl_seconds: float = SNAPSHOT_TTL_SECONDS) -> None:
        self._ttl_seconds = ttl_seconds
        self._lock = threading.Lock()
        self._snapshots: dict[Hashable, tuple[float, list[int]]] = {}

    def ordered_ids(self, key: Hashable, rows: list[dict[str, Any]]) -> list[int]:
        """返回这批过滤结果稳定的有序 id 列表；快照在 TTL 内复用，过期重建。"""
        now = time.monotonic()
        with self._lock:
            cached = self._snapshots.get(key)
            if cached is None or now - cached[0] > self._ttl_seconds:
                cached = (now, sorted(_row_id(row) for row in rows))
                self._snapshots[key] = cached
            return list(cached[1])

    def clear(self) -> None:
        with self._lock:
            self._snapshots.clear()


page_snapshots = PageSnapshots()


def paginate(
    rows: list[dict[str, Any]],
    *,
    page: int,
    size: int,
    cache_key: Hashable,
    revision: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """对过滤后的全量行分页，返回 (当前页记录, 过滤后总数)。

    rows 是过滤后的全量，次序由本函数按 id 固定，调用方不用自己排序；
    cache_key 用来区分不同模块、不同过滤条件的快照，一般传 (模块名, 各过滤参数)；
    revision 是数据的写操作版本号，有新增、状态流转时递增，快照随之重算；
    删除不要递增 revision——翻页期间的并发删除由快照吸收，记录不会跨页重复。
    """
    check_page_params(page, size)
    ids = page_snapshots.ordered_ids((PAGING_SPEC_VERSION, revision, cache_key), rows)
    total = len(ids)
    start = (page - 1) * size
    page_ids = ids[start:start + size]  # 全量里只切这一次
    by_id = {_row_id(row): row for row in rows}
    # 翻页期间被并发删除的记录直接从本页消失，不会换个页码再冒出来。
    items = [by_id[row_id] for row_id in page_ids if row_id in by_id]
    return items, total
