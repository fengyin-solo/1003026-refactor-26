"""防雷接地业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.services.common import list_all_entries, list_module_entries
from app.store import store

MODULE = "lightningprot"
REQUIRED_FIELDS = ["装置编号", "所属站点", "接地电阻"]
STATUS_ORDER = ["合格", "电阻超标", "模块劣化", "已更换"]
ACTION_RULES = {"记录超标": "电阻超标", "记录劣化": "模块劣化", "安排更换": "已更换"}
NEGATIVE_ACTIONS = []

KEYWORD_FIELD = '装置编号'


class LightningprotService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        """过滤条件各模块不同，分页与总数全平台共用一套口径。"""
        return list_module_entries(
            MODULE, KEYWORD_FIELD, keyword=keyword, status=status, page=page, size=size
        )

    def export_entries(self) -> tuple[list[dict[str, Any]], int]:
        """导出走全量清单，不受分页上限约束。"""
        return list_all_entries(MODULE)

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        entry = {field: values.get(field) for field in REQUIRED_FIELDS}
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        return store.append(MODULE, entry), []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        with store.lock:
            entry = store.find(MODULE, entry_id)
            if entry is None:
                return None, f"防雷装置 {entry_id} 不存在或已归档"
            if action not in ACTION_RULES:
                return None, f"动作「{action}」不属于防雷接地可执行范围"
            target = ACTION_RULES[action]
            if target not in STATUS_ORDER:
                return None, f"目标状态「{target}」不在允许的状态序列里"
            entry["status"] = target
            entry["pending"] = target != STATUS_ORDER[-1]
            entry["abnormal"] = action in NEGATIVE_ACTIONS
            return entry, f"防雷装置已{action}"
