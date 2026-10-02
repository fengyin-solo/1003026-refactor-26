"""内存数据仓库：给每个业务模块准备一份可筛选、可流转的示例数据。

真实项目里这里会换成数据库访问层；当前实现只依赖标准库，保证克隆下来就能起。
读写共用一把锁：列表拿到的是同一时刻的快照，并发增删不会把同一条记录切进两页。
"""
from __future__ import annotations

import threading
from typing import Any

from app.seed import SEED_ROWS


class Store:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self._tables: dict[str, list[dict[str, Any]]] = {
            name: [dict(row) for row in rows] for name, rows in SEED_ROWS.items()
        }

    def module_names(self) -> list[str]:
        return sorted(self._tables)

    def snapshot(self, module: str) -> list[dict[str, Any]]:
        """拷贝模块当前的全量记录：一次查询内的过滤、计数、切片都基于这份快照。"""
        with self.lock:
            return [dict(row) for row in self._tables.setdefault(module, [])]

    def find(self, module: str, entry_id: int) -> dict[str, Any] | None:
        with self.lock:
            for row in self._tables.setdefault(module, []):
                if int(row.get("id", 0)) == entry_id:
                    return row
            return None

    def append(self, module: str, entry: dict[str, Any]) -> dict[str, Any]:
        """加锁分配 id 再写入：并发登记不会拿到同一个 id，分页顺序才稳。"""
        with self.lock:
            rows = self._tables.setdefault(module, [])
            entry["id"] = max((int(row.get("id", 0)) for row in rows), default=0) + 1
            rows.append(entry)
            return dict(entry)

    def delete(self, module: str, entry_id: int) -> bool:
        """加锁删除一条记录；与快照共用一把锁，删与查不会互相穿插。"""
        with self.lock:
            rows = self._tables.setdefault(module, [])
            for index, row in enumerate(rows):
                if int(row.get("id", 0)) == entry_id:
                    del rows[index]
                    return True
            return False

    def overview(self) -> dict[str, object]:
        modules: list[dict[str, object]] = []
        for name in self.module_names():
            rows = self.snapshot(name)
            modules.append({
                "name": name,
                "created": len(rows),
                "pending": sum(1 for row in rows if row.get("pending")),
                "abnormal": sum(1 for row in rows if row.get("abnormal")),
            })
        cards = [
            {"label": "业务模块", "value": len(modules)},
            {"label": "今日新增", "value": sum(int(item["created"]) for item in modules)},
            {"label": "待处理", "value": sum(int(item["pending"]) for item in modules)},
            {"label": "异常量", "value": sum(int(item["abnormal"]) for item in modules)},
        ]
        return {"cards": cards, "modules": modules}


store = Store()
