"""驗證 backup/restore 保護邏輯（內容持久化）：
- 空/較貧 DB 啟動時，會從較豐裕的 backup 回填
- 不讓「比較空的 DB」覆寫「比較豐裕的 backup」
- restore 遇到 schema 有差異的 row 會跳過而非整表/整庫崩潰
"""
import json

import pytest

from marketing_system import config as cfg
from marketing_system.database import (
    DB_TABLES,
    _backup_content_score,
    _dump_to_json,
    _restore_from_backup,
    init_db,
)


def _write_backup(**overrides):
    data = {t: [] for t in DB_TABLES}
    for t, rows in overrides.items():
        data[t] = rows
    cfg.DATABASE_BACKUP_PATH.write_text(json.dumps(data), encoding="utf-8")
    return data


@pytest.fixture(autouse=True)
def _reset(tmp_path, monkeypatch):
    # 每次測試用獨立 DB 檔與 backup 檔，避免污染其他測試
    monkeypatch.setattr(cfg, "DATABASE_PATH", tmp_path / "marketing.db")
    monkeypatch.setattr(cfg, "DATABASE_BACKUP_PATH", tmp_path / "db_backup.json")
    monkeypatch.setattr(cfg, "BACKUP_DIR", tmp_path)
    import marketing_system.database as db
    monkeypatch.setattr(db, "DATABASE_PATH", cfg.DATABASE_PATH)
    monkeypatch.setattr(db, "DATABASE_BACKUP_PATH", cfg.DATABASE_BACKUP_PATH)
    monkeypatch.setattr(db, "_try_git_push", lambda: None)
    init_db()


class TestBackupProtection:
    def test_empty_db_starts_with_seed_tables(self):
        from marketing_system.database import fetch
        assert fetch("SELECT COUNT(*) c FROM novels")[0]["c"] >= 3

    def test_dump_does_not_overwrite_richer_backup(self):
        _write_backup(feed_posts=[{
            "id": 1, "content": "rich content", "post_type": "story",
            "author": "翔川", "created_at": "2026-09-29", "user_id": None,
        }])
        # 現 DB 剛 init（內容 0），backup 較豐裕 → dump 必須跳過、不得覆寫
        _dump_to_json()
        after = json.loads(cfg.DATABASE_BACKUP_PATH.read_text("utf-8"))
        assert len(after["feed_posts"]) == 1, "較豐裕的 backup 不該被空 DB 覆寫"

    def test_dump_updates_when_db_richer(self):
        from marketing_system.database import execute
        execute("INSERT INTO feed_posts (content, post_type) VALUES (?,?)",
                ["r1", "story"])
        _dump_to_json()
        after = json.loads(cfg.DATABASE_BACKUP_PATH.read_text("utf-8"))
        assert len(after["feed_posts"]) >= 1

    def test_restore_skips_schema_mismatch_rows(self):
        _write_backup(feed_posts=[
            # 正常 row
            {"id": 1, "content": "ok row", "post_type": "story",
             "author": "翔川", "created_at": "2026-09-29"},
            # 帶舊 schema 欄位（mapped 到新欄位，應容忍還原）
            {"id": 2, "content": "bad row", "body": "legacy", "chapter_no": 7,
             "post_type": "story", "author": "翔川", "created_at": "2026-09-29"},
            # 與現表完全沒有共同欄位的 row → 應完全跳過
            {"id": 3, "legacy_only": 1, "weird_col": 2},
        ])
        _restore_from_backup()
        from marketing_system.database import fetch
        rows = fetch("SELECT * FROM feed_posts")
        contents = [r["content"] for r in rows]
        assert "ok row" in contents
        assert "bad row" in contents  # 多餘欄位被容忍，必須的內容活下來
        assert len(rows) == 2  # 無共同欄位那 row 被過濾跳過

    def test_restore_maps_legacy_column_names(self):
        # 舊 schema 的 novel_chapters（chapter_no/body）應對映成新欄位成功還原
        _write_backup(novel_chapters=[{
            "id": 1, "novel_id": 1, "chapter_no": 1, "title": "第一章",
            "body": "內文", "tokens": 0, "created_at": "2026-09-29",
        }])
        _restore_from_backup()
        from marketing_system.database import fetch
        rows = fetch("SELECT * FROM novel_chapters")
        assert len(rows) == 1
        assert rows[0]["chapter_number"] == 1
        assert rows[0]["content"] == "內文"

    def test_init_restores_rich_backup_into_empty_db(self):
        from marketing_system.database import execute, fetch
        execute("INSERT INTO feed_posts (content, post_type) VALUES (?,?)",
                ["before", "story"])
        _dump_to_json()  # backup 現在有 1 筆
        # 模擬檔案被清掉（Render 無持久碟 / deploy 後）
        cfg.DATABASE_PATH.unlink()
        db_file = cfg.DATABASE_PATH
        monkey = None
        import marketing_system.database as dbmod
        # init_db 讀 module global；直接用原函數即可（路徑已 monkeypatch）
        init_db()
        rows = fetch("SELECT * FROM feed_posts")
        assert any(r["content"] == "before" for r in rows), "空 DB 啟動應從 backup 回填內容"