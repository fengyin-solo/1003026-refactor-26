"""开关电源业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.services.common import list_all_entries, list_module_entries
from app.store import store

MODULE = "rectifier"
REQUIRED_FIELDS = ["电源编号", "额定功率", "所属站点"]
STATUS_ORDER = ["正常", "模块缺失", "输出异常", "已更换"]
ACTION_RULES = {"记录缺失": "模块缺失", "记录异常": "输出异常", "安排更换": "已更换"}
NEGATIVE_ACTIONS = []

KEYWORD_FIELD = '电源编号'


class RectifierService:
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
                return None, f"开关电源 {entry_id} 不存在或已归档"
            if action not in ACTION_RULES:
                return None, f"动作「{action}」不属于开关电源可执行范围"
            target = ACTION_RULES[action]
            if target not in STATUS_ORDER:
                return None, f"目标状态「{target}」不在允许的状态序列里"
            entry["status"] = target
            entry["pending"] = target != STATUS_ORDER[-1]
            entry["abnormal"] = action in NEGATIVE_ACTIONS
            return entry, f"开关电源已{action}"
