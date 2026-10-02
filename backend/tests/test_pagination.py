"""分页统一口径的回归校验。

运行方式：cd backend && python3 -m pytest tests/test_pagination.py -q
"""
from __future__ import annotations

import threading

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.pagination import PageParamsError, paginate, parse_page_params
from app.services.common import list_all_entries, list_module_entries
from app.store import store

SCRATCH = "test_scratch"


def reset_scratch(count: int) -> None:
    with store.lock:
        store._tables[SCRATCH] = [
            {"id": i, "status": "正常" if i % 2 else "异常", "编号": f"T-{i:04d}"}
            for i in range(1, count + 1)
        ]


@pytest.fixture(autouse=True)
def scratch_cleanup():
    yield
    with store.lock:
        store._tables.pop(SCRATCH, None)


def test_total_counts_filtered_full_set():
    reset_scratch(30)
    items, total = list_module_entries(SCRATCH, "编号", keyword=None, status="正常", page=1, size=5)
    assert total == 15  # 过滤后的全量，不是当前页条数
    assert len(items) == 5
    items, total = list_module_entries(SCRATCH, "编号", keyword=None, status="正常", page=3, size=5)
    assert total == 15
    assert len(items) == 5
    items, total = list_module_entries(SCRATCH, "编号", keyword=None, status="正常", page=4, size=5)
    assert total == 15
    assert items == []  # 越界页返回空，但总数照旧


def test_keyword_filter_matches_module_field():
    reset_scratch(30)
    items, total = list_module_entries(SCRATCH, "编号", keyword="T-0030", status=None, page=1, size=5)
    assert total == 1
    assert items[0]["编号"] == "T-0030"
    items, total = list_module_entries(SCRATCH, "编号", keyword="T-002", status=None, page=1, size=5)
    assert total == 10  # 子串匹配：T-0020 到 T-0029


def test_paging_twice_no_dup_no_gap():
    reset_scratch(30)
    for _ in range(2):  # 同一批数据翻两遍，结果必须一致
        seen: list[int] = []
        page = 1
        while True:
            items, total = list_module_entries(SCRATCH, "编号", keyword=None, status=None, page=page, size=7)
            assert total == 30
            if not items:
                break
            seen.extend(row["id"] for row in items)
            page += 1
        assert seen == list(range(1, 31))  # 不重复、不遗漏、顺序确定


def test_page_size_cap_and_bounds():
    params = parse_page_params(1, settings.page_size_max)
    assert params.size == settings.page_size_max
    with pytest.raises(PageParamsError, match=f"每页最多 {settings.page_size_max} 条"):
        parse_page_params(1, settings.page_size_max + 1)
    with pytest.raises(PageParamsError, match="页码从 1 开始"):
        parse_page_params(0, 20)
    with pytest.raises(PageParamsError, match="至少为 1"):
        parse_page_params(1, 0)
    with pytest.raises(PageParamsError):
        list_module_entries(SCRATCH, "编号", keyword=None, status=None, page=1, size=10**6)


def test_paginate_sorts_before_slicing():
    rows = [{"id": 3}, {"id": 1}, {"id": 2}]
    items, total = paginate(rows, parse_page_params(1, 2))
    assert [row["id"] for row in items] == [1, 2]
    assert total == 3


def test_export_returns_full_set_above_page_cap():
    reset_scratch(settings.page_size_max + 50)
    items, total = list_all_entries(SCRATCH)
    assert total == settings.page_size_max + 50
    assert len(items) == total  # 导出不再被写死的页大小截断
    assert [row["id"] for row in items] == sorted(row["id"] for row in items)


def test_delete_between_pages_never_on_two_pages():
    reset_scratch(5)
    page1, total1 = list_module_entries(SCRATCH, "编号", keyword=None, status=None, page=1, size=2)
    assert [row["id"] for row in page1] == [1, 2]
    assert total1 == 5
    assert store.delete(SCRATCH, 1) is True
    page2, total2 = list_module_entries(SCRATCH, "编号", keyword=None, status=None, page=2, size=2)
    assert total2 == 4
    assert not {row["id"] for row in page1} & {row["id"] for row in page2}


def test_concurrent_paging_while_deleting_stays_coherent():
    reset_scratch(200)
    size = 10
    errors: list[str] = []
    stop = threading.Event()

    def reader(page: int) -> None:
        while not stop.is_set():
            items, total = list_module_entries(
                SCRATCH, "编号", keyword=None, status=None, page=page, size=size
            )
            ids = [row["id"] for row in items]
            if len(ids) != len(set(ids)):
                errors.append(f"page {page}: 同一页内出现重复记录 {ids}")
            if ids != sorted(ids):
                errors.append(f"page {page}: 页内顺序不稳定 {ids}")
            expected = max(0, min(size, total - (page - 1) * size))
            if len(items) != expected:
                errors.append(f"page {page}: 总数 {total} 与切片条数 {len(items)} 对不上")

    def deleter() -> None:
        for entry_id in range(1, 101):
            store.delete(SCRATCH, entry_id)

    deleter_thread = threading.Thread(target=deleter)
    readers = [threading.Thread(target=reader, args=(page,)) for page in (1, 2, 3)]
    for thread in readers:
        thread.start()
    deleter_thread.start()
    deleter_thread.join()
    stop.set()
    for thread in readers:
        thread.join()
    assert errors == []


client = TestClient(app)


def test_api_list_envelope_and_cap():
    response = client.get("/api/site", params={"page": 1, "size": 2})
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"items", "total", "page", "size"}  # 对外字段名照旧
    assert payload["page"] == 1 and payload["size"] == 2
    assert payload["total"] >= len(payload["items"])

    response = client.get("/api/site", params={"size": settings.page_size_max + 1})
    assert response.status_code == 400
    assert f"每页最多 {settings.page_size_max} 条" in response.json()["detail"]

    response = client.get("/api/site", params={"page": 0})
    assert response.status_code == 400
    assert "页码从 1 开始" in response.json()["detail"]


def test_api_export_shape_unchanged():
    response = client.get("/api/site/export")
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"module", "total", "items"}  # 历史导出包不动
    assert payload["module"] == "site"
    assert payload["total"] == len(payload["items"])
