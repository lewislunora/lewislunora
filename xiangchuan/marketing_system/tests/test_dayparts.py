"""每日內容的台灣時段排程。"""

from datetime import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Taipei")


def _at(h, m=5):
    return datetime(2026, 10, 5, h, m, tzinfo=TZ)


def test_current_slot_boundaries():
    from marketing_system.services import dayparts as dp
    assert dp.current_slot(_at(6))["key"] == "dawn"
    assert dp.current_slot(_at(9))["key"] == "morning"
    assert dp.current_slot(_at(13))["key"] == "noon"
    assert dp.current_slot(_at(16))["key"] == "afternoon"
    assert dp.current_slot(_at(19))["key"] == "evening"
    assert dp.current_slot(_at(23))["key"] == "night"
    assert dp.current_slot(_at(3))["key"] == "night"


def test_short_targets_its_slots():
    """短文排程在清晨／中午／傍晚，每個時段只產一次。"""
    from marketing_system.services import dayparts as dp
    assert dp.should_run("short", _at(6))["slot"] == "dawn"
    assert dp.should_run("short", _at(13))["slot"] == "noon"
    assert dp.should_run("short", _at(19))["slot"] == "evening"
    # 產過清晨後，上午不該再產（要等到中午時段）
    dp.mark_slot("short", "dawn", day="2026-10-05")
    assert dp.should_run("short", _at(9), day="2026-10-05")["run"] is False
    assert dp.should_run("short", _at(13), day="2026-10-05")["run"] is True


def test_seo_targets_morning_and_no_duplicate():
    from marketing_system.services import dayparts as dp
    assert dp.should_run("seo", _at(9))["slot"] == "morning"
    dp.mark_slot("seo", "morning", day="2026-10-05")
    # 當天已產過，之後任何時段都不該再產（長文一天一篇）
    for h in (13, 16, 20, 22):
        gate = dp.should_run("seo", _at(h), day="2026-10-05")
        assert gate["run"] is False, f"{h} 時不該再產長文（{gate['reason']}）"


def test_marked_slot_not_repeated():
    from marketing_system.services import dayparts as dp
    dp.mark_slot("short", "dawn", day="2026-10-05")
    assert dp.should_run("short", _at(6))["run"] is False
    assert "dawn" in dp.done_slots("short", "2026-10-05")


def test_missed_slot_is_caught_up():
    """服務休眠錯過的時段，下一輪要補產，當日產量不減。"""
    from marketing_system.services import dayparts as dp
    # 短文清晨（5-8）沒產，10 點時應補產
    gate = dp.should_run("short", _at(10))
    assert gate["run"] is True and gate["slot"] == "dawn"


def test_overview_shape():
    from marketing_system.services import dayparts as dp
    o = dp.overview()
    assert o["tz"] == "Asia/Taipei"
    assert set(o["plan"]) == {"short", "seo", "novel"}
    assert o["current"]["label"]


def test_dayparts_endpoint():
    from fastapi.testclient import TestClient
    from marketing_system.api.server import app
    d = TestClient(app).get("/api/dayparts").json()
    assert d["tz"] == "Asia/Taipei" and "current" in d
