"""排程器鉤子與自動引擎的守護測試。

重點 regression：舊實作 monkey-patch scheduler._loop，會把 _loop 內的
_keep_alive()／_govdata_sync()／_dump_backup_snapshot() 覆蓋掉，
導致 Render 免費層休眠、內容引擎停產。這裡驗證：
- _loop 本體沒被 monkey-patch（保活與快照仍在）
- add_hook 依排程頻率觸發，且單一鉤子失敗不會影響其他鉤子
- auto_status 能回報 pings 與最後執行結果
"""
import pytest

from marketing_system.scheduler import ContentScheduler


def test_loop_not_monkey_patched():
    """_register_promo_task 執行後，_loop 必須仍是 ContentScheduler 自己的方法。"""
    from marketing_system.api import server
    server._register_promo_task()
    assert "patched_loop" not in ContentScheduler._loop.__qualname__
    assert ContentScheduler._loop.__qualname__ == "ContentScheduler._loop"


def test_keep_alive_and_snapshots_still_in_loop():
    src = __import__("inspect").getsource(ContentScheduler._loop)
    assert "_keep_alive()" in src, "保活被覆蓋會讓 Render 免費層休眠"
    assert "_govdata_sync()" in src
    assert "_dump_backup_snapshot()" in src
    assert "_run_hooks()" in src


def test_hooks_fire_on_schedule_and_isolate_failures():
    sched = ContentScheduler()
    calls = []

    sched.add_hook(15, "ok_hook", lambda: calls.append("ok"))
    sched.add_hook(15, "bad_hook", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    sched.add_hook(30, "other", lambda: calls.append("other"))

    sched._ping_count = 15
    sched._run_hooks()
    assert calls == ["ok"], "good hook 應執行；bad hook 失敗不應影響它"

    sched._ping_count = 30
    sched._run_hooks()
    assert calls == ["ok", "ok", "other"]

    status = sched.auto_status()
    assert status["pings"] == 30
    assert status["ticks"]["ok_hook"]["ok"] is True
    assert status["ticks"]["bad_hook"]["ok"] is False
    assert "boom" in status["ticks"]["bad_hook"]["error"]
    assert set(status["hooks"]) == {"ok_hook", "bad_hook", "other"}


def test_hooks_not_fired_off_schedule():
    sched = ContentScheduler()
    calls = []
    sched.add_hook(15, "h", lambda: calls.append(1))
    sched._ping_count = 7
    sched._run_hooks()
    assert calls == []


def test_dump_backup_snapshot_calls_database_dump(monkeypatch):
    import marketing_system.database as db
    called = []
    monkeypatch.setattr(db, "_dump_to_json", lambda: called.append(1))
    ContentScheduler()._dump_backup_snapshot()
    assert called == [1], "定期快照沒寫出來，流量/內容會隨 ephemeral 磁碟消失"


def test_dump_backup_snapshot_swallows_errors(monkeypatch):
    import marketing_system.database as db

    def boom():
        raise RuntimeError("disk full")

    monkeypatch.setattr(db, "_dump_to_json", boom)
    ContentScheduler()._dump_backup_snapshot()  # 不應拋出


def test_status_endpoint_exposes_auto_engine(client):
    res = client.get("/api/status")
    assert res.status_code == 200
    body = res.json()
    assert "auto_engine" in body
    assert "pings" in body["auto_engine"] and "ticks" in body["auto_engine"]