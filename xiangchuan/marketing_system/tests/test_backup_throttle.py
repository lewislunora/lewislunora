"""備份快照節流與批次寫入的測試。

regression：原本 execute() 每次寫入都整份 _dump_to_json()，
大量列寫入（gov_rows 一筆資料集最多 6 萬列）會變 O(n²) 拖垮服務。
"""
import json

import marketing_system.database as db
from marketing_system.database import execute, execute_many, fetch, fetch_one


def _count_dumps(monkeypatch):
    calls = []
    monkeypatch.setattr(db, "_dump_to_json", lambda: calls.append(1))
    db._last_dump_at["ts"] = 0.0
    return calls


def test_writes_are_dump_debounced(monkeypatch):
    calls = _count_dumps(monkeypatch)
    for i in range(20):
        execute("INSERT INTO geo_cache (ip, country, city) VALUES (?,?,?)", [f"1.1.1.{i}", "TW", "TW"])
    assert len(calls) == 1, f"20 次寫入不該 dump 20 次，實際 {len(calls)}"


def test_debounce_window_expires(monkeypatch):
    calls = _count_dumps(monkeypatch)
    execute("INSERT INTO geo_cache (ip, country, city) VALUES (?,?,?)", ["9.9.9.1", "TW", "TW"])
    assert len(calls) == 1
    db._last_dump_at["ts"] -= db.DUMP_DEBOUNCE_SECONDS + 1
    execute("INSERT INTO geo_cache (ip, country, city) VALUES (?,?,?)", ["9.9.9.2", "TW", "TW"])
    assert len(calls) == 2


def test_reads_do_not_dump(monkeypatch):
    calls = _count_dumps(monkeypatch)
    fetch("SELECT * FROM geo_cache")
    fetch_one("SELECT COUNT(*) AS c FROM geo_cache")
    assert calls == []


def test_execute_many_dumps_once(monkeypatch):
    calls = _count_dumps(monkeypatch)
    n = execute_many(
        "INSERT INTO gov_rows (nid, row_idx, payload) VALUES (?,?,?)",
        [[f"n{i}", i, json.dumps({"a": i})] for i in range(500)],
    )
    assert n == 500
    assert len(calls) == 1, f"500 列批次只應 dump 1 次，實際 {len(calls)}"
    assert fetch_one("SELECT COUNT(*) AS c FROM gov_rows WHERE nid='n499'")["c"] == 1


def test_execute_many_empty_is_noop(monkeypatch):
    calls = _count_dumps(monkeypatch)
    assert execute_many("INSERT INTO gov_rows (nid, row_idx, payload) VALUES (?,?,?)", []) == 0
    assert calls == []


def test_govdata_ingest_uses_bulk_insert():
    """ingest 不得逐列呼叫 execute（否則大資料集會再次變 O(n²)）。"""
    import inspect

    from marketing_system.services import govdata as gd
    src = inspect.getsource(gd.ingest)
    assert "execute_many(" in src, "gov_rows 必須批次寫入"
    # 逐列 INSERT 的 execute 呼叫不該存在（DELETE 與 gov_datasets upsert 可以；
    # 收集欄位的讀取迴圈可以有）
    assert 'execute(\n                "INSERT INTO gov_rows' not in src
    assert 'execute(\n                "INSERT INTO gov_rows (nid, row_idx, payload) VALUES (?,?,?)"' not in src
