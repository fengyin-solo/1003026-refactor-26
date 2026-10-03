"""分页共用口径的验收测试：总数、单次切片、页大小上限、稳定翻页与并发删除。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import pagination
from app.config import settings
from app.main import app
from app.pagination import PageParamsError, paginate, page_snapshots
from app.store import store


@pytest.fixture(autouse=True)
def clear_snapshots():
    page_snapshots.clear()
    yield
    page_snapshots.clear()


def make_rows(count: int) -> list[dict]:
    return [{"id": i, "status": "运行中" if i % 2 else "退服中"} for i in range(1, count + 1)]


class TestPaginate:
    def test_total_counts_filtered_full_set(self):
        items, total = paginate(make_rows(45), page=1, size=20, cache_key=("m",))
        assert total == 45
        assert len(items) == 20

    def test_second_page_lines_up(self):
        rows = make_rows(45)
        page1, _ = paginate(rows, page=1, size=20, cache_key=("m",))
        page2, _ = paginate(rows, page=2, size=20, cache_key=("m",))
        assert [row["id"] for row in page1] == list(range(1, 21))
        assert [row["id"] for row in page2] == list(range(21, 41))

    def test_paging_through_twice_has_no_dup_and_no_gap(self):
        rows = make_rows(45)
        seen = []
        for _ in range(2):  # 同一批数据翻两遍
            for page in (1, 2, 3):
                items, _ = paginate(rows, page=page, size=20, cache_key=("m",))
                seen.append([row["id"] for row in items])
        first, second = seen[:3], seen[3:]
        assert first == second
        flat = [row_id for page_ids in first for row_id in page_ids]
        assert flat == [row["id"] for row in rows]
        assert len(flat) == len(set(flat))

    def test_size_over_max_is_rejected_with_reason(self):
        with pytest.raises(PageParamsError, match=str(settings.page_size_max)):
            paginate(make_rows(5), page=1, size=settings.page_size_max + 1, cache_key=("m",))

    @pytest.mark.parametrize("page,size", [(0, 20), (-1, 20), (1, 0), (1, -5)])
    def test_invalid_params_are_rejected(self, page, size):
        with pytest.raises(PageParamsError):
            paginate(make_rows(5), page=page, size=size, cache_key=("m",))

    def test_concurrent_delete_never_puts_record_on_two_pages(self):
        rows = make_rows(45)
        page1, total1 = paginate(rows, page=1, size=20, cache_key=("m",))
        assert total1 == 45
        deleted = rows.pop(3)  # 翻页期间有人删掉了第一页里的一条
        page2, total2 = paginate(rows, page=2, size=20, cache_key=("m",))
        ids1 = {row["id"] for row in page1}
        ids2 = {row["id"] for row in page2}
        assert not ids1 & ids2, "同一条记录不能同时出现在两页"
        assert deleted["id"] not in ids2
        assert total2 == 45  # 快照有效期内总数按取数时的过滤全量算，不随删除漂移

    def test_spec_version_bump_recomputes_cached_pages(self, monkeypatch):
        rows = make_rows(5)
        _, total_before = paginate(rows, page=1, size=20, cache_key=("m",))
        rows.pop(0)
        _, total_cached = paginate(rows, page=1, size=20, cache_key=("m",))
        assert total_before == total_cached == 5  # 旧口径快照仍在用
        monkeypatch.setattr(pagination, "PAGING_SPEC_VERSION", pagination.PAGING_SPEC_VERSION + 1)
        _, total_after = paginate(rows, page=1, size=20, cache_key=("m",))
        assert total_after == 4  # 口径版本变化后按新口径重算

    def test_revision_bump_recomputes_snapshot(self):
        rows = make_rows(5)
        _, total_before = paginate(rows, page=1, size=20, cache_key=("m",), revision=1)
        rows.append({"id": 6, "status": "运行中"})
        _, total_same = paginate(rows, page=1, size=20, cache_key=("m",), revision=1)
        assert total_before == total_same == 5  # 版本没变，快照照旧
        _, total_new = paginate(rows, page=1, size=20, cache_key=("m",), revision=2)
        assert total_new == 6  # 写操作递增版本后按新数据重算


class TestServicePaging:
    def setup_method(self):
        self.table = store.rows("site")
        self.backup = list(self.table)

    def teardown_method(self):
        self.table[:] = self.backup

    def seed_rows(self, count: int) -> None:
        self.table[:] = [
            {"id": i, "status": "运行中", "pending": True, "abnormal": False, "基站编号": f"S-{i:04d}"}
            for i in range(1, count + 1)
        ]

    def test_new_entry_shows_up_immediately(self):
        from app.services.site import SiteService

        service = SiteService()
        self.seed_rows(3)
        _, total_before = service.list_entries()
        assert total_before == 3
        entry, missing = service.create_entry({"基站编号": "S-0004", "基站名称": "新站", "基站类型": "宏站"})
        assert not missing
        items, total_after = service.list_entries()
        assert total_after == 4
        assert entry in items  # 登记后不用等快照过期就能翻到

    def test_delete_during_paging_keeps_pages_disjoint(self):
        from app.services.site import SiteService

        service = SiteService()
        self.seed_rows(45)
        page1, _ = service.list_entries(size=20)
        self.table[:] = [row for row in self.table if row["id"] != 2]  # 并发删掉第一页里的一条
        page2, _ = service.list_entries(page=2, size=20)
        ids1 = {row["id"] for row in page1}
        ids2 = {row["id"] for row in page2}
        assert not ids1 & ids2, "同一条记录不能同时出现在两页"
        assert min(ids2) == 21, "删除不会把后一页的记录顶错位"


client = TestClient(app)


class TestListApi:
    def test_response_fields_stay_the_same(self):
        payload = client.get("/api/site").json()
        assert set(payload) == {"items", "total", "page", "size"}

    def test_oversized_page_returns_400_with_reason(self):
        response = client.get(f"/api/site?size={settings.page_size_max + 1}")
        assert response.status_code == 400
        assert str(settings.page_size_max) in response.json()["detail"]

    @pytest.mark.parametrize("query", ["page=0", "size=0"])
    def test_invalid_params_return_400(self, query):
        assert client.get(f"/api/site?{query}").status_code == 400

    def test_export_keeps_full_result_beyond_page_cap(self):
        table = store.rows("site")
        backup = list(table)
        try:
            table[:] = [{"id": i, "status": "运行中"} for i in range(1, settings.page_size_max + 50)]
            response = client.get("/api/site/export")
            assert response.status_code == 200
            payload = response.json()
            assert set(payload) == {"module", "total", "items"}
            assert payload["total"] == len(table)
            assert len(payload["items"]) == len(table)
            # 同样的量走列表接口会被页大小上限拦下
            assert client.get(f"/api/site?size={len(table)}").status_code == 400
        finally:
            table[:] = backup
