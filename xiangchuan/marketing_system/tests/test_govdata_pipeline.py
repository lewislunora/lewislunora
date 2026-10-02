"""govdata 全自動管線的離線測試：候選挑選、容量汰舊、最近分析清單、API。"""
import json

from fastapi.testclient import TestClient

from marketing_system.services import govdata as gd
from marketing_system.database import execute, fetch, fetch_one, init_db


def _seed_catalog():
    execute(
        "INSERT INTO gov_catalog (nid, title, agency, category, topic, freq, charge, license, "
        "formats, dl_url, qty, description, view_times, synced_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?, datetime('now'))",
        ["n1", "高熱門 CSV AQI", "環保署", "環境", "空氣", "每日", "", "", "CSV", "https://x/a.csv", "1", "d", 99999],
    )
    execute(
        "INSERT INTO gov_catalog (nid, title, agency, category, topic, freq, charge, license, "
        "formats, dl_url, qty, description, view_times, synced_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?, datetime('now'))",
        ["n2", "低熱門 JSON 人口", "主計處", "統計", "人口", "每季", "", "", "JSON", "https://x/b.json", "2", "d", 10],
    )
    execute(
        "INSERT INTO gov_catalog (nid, title, agency, category, topic, freq, charge, license, "
        "formats, dl_url, qty, description, view_times, synced_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?, datetime('now'))",
        ["n3", "無連結格式", "某局", "其他", "其他", "", "", "", "XML", "https://x/c.xml", "3", "d", 50000],
    )
    execute(
        "INSERT INTO gov_catalog (nid, title, agency, category, topic, freq, charge, license, "
        "formats, dl_url, qty, description, view_times, synced_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?, datetime('now'))",
        ["n4", "已匯入過的", "某局", "其他", "其他", "", "", "", "CSV", "https://x/d.csv", "0", "d", 88888],
    )
    execute(
        "INSERT INTO gov_datasets (nid, title, agency, row_count, status, ingested_at) "
        "VALUES ('n4','已匯入過的','某局',10,'ok', datetime('now'))",
    )


def test_pick_candidates_orders_preferred_then_views():
    _seed_catalog()
    cands = gd.pick_candidates(limit=3)
    nids = [c["nid"] for c in cands]
    # n1 (CSV, 高瀏覽) 優先；n3 無友善格式但瀏覽次數高；n4 已匯入排除
    assert nids == ["n1", "n2", "n3"], nids
    assert all(c["preferred"] is True or c["preferred"] is False for c in cands)


def test_pick_candidates_excludes_failed_recent_but_retries_old():
    _seed_catalog()
    execute(
        "INSERT INTO gov_datasets (nid, title, agency, row_count, status, note, ingested_at) "
        "VALUES ('n2','x','y',0,'failed','boom', datetime('now','-30 days'))",
    )
    cands = gd.pick_candidates(limit=5)
    nids = [c["nid"] for c in cands]
    assert "n2" in nids  # 失敗超過 7 天可重試
    assert "n4" not in nids


def test_prune_if_needed_removes_oldest_when_over_budget():
    for i in range(5):
        execute(
            "INSERT INTO gov_datasets (nid, title, agency, row_count, status, ingested_at) "
            "VALUES (?,?,'a',1000,'ok', datetime('now'))",
            [f"p{i}", f"t{i}"],
        )
        for j in range(3):
            execute(
                "INSERT INTO gov_rows (nid, row_idx, payload) VALUES (?,?,?)",
                [f"p{i}", j, json.dumps({"x": j})],
            )
    assert fetch_one("SELECT COUNT(*) AS c FROM gov_rows")["c"] == 15
    res = gd.prune_if_needed(budget=8)  # 8 < 15 → 刪到 80%*8=6.4 → 保留最少
    assert res["pruned"] >= 1
    assert fetch_one("SELECT COUNT(*) AS c FROM gov_rows")["c"] < 15
    assert fetch_one("SELECT COUNT(*) AS c FROM gov_datasets WHERE status='pruned'")["c"] >= 1


def test_recent_analyzed_lists_ok_datasets():
    execute(
        "INSERT INTO gov_datasets (nid, title, agency, columns_json, row_count, status, ingested_at) "
        "VALUES ('r1','報告一','機構','[\"a\",\"b\"]',5,'ok', datetime('now'))",
    )
    execute(
        "INSERT INTO gov_datasets (nid, title, agency, columns_json, row_count, status, ingested_at) "
        "VALUES ('bad','失敗的','機構','[]',0,'failed', datetime('now'))",
    )
    items = gd.recent_analyzed(limit=5)
    nids = [x["nid"] for x in items]
    assert "r1" in nids and "bad" not in nids
    r1 = items[nids.index("r1")]
    assert r1["columns"] == ["a", "b"] and r1["row_count"] == 5


def test_recent_api_endpoint(client: TestClient):
    res = client.get("/api/govdata/recent?limit=3")
    assert res.status_code == 200
    body = res.json()
    assert "items" in body and isinstance(body["items"], list)