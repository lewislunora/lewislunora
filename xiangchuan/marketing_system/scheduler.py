import os
import time
import logging
import threading
import urllib.request
from datetime import datetime
from .database import fetch, execute

logger = logging.getLogger(__name__)

RENDER_SELF_URL = os.getenv("RENDER_SELF_URL", "https://lewislunora.onrender.com")


class ContentScheduler:
    def __init__(self, platform_connectors=None):
        self.running = False
        self.thread = None
        self.connectors = platform_connectors or {}
        self._ping_count = 0
        # (every, name, fn)：由 server 註冊的排程鉤子（內容引擎等）
        self.hooks = []
        self.last_ticks = {}

    def add_hook(self, every: int, name: str, fn):
        """註冊排程鉤子：每 every 次迴圈（1 次 ≈ 60 秒）執行一次。"""
        self.hooks.append((int(every), name, fn))

    def _run_hooks(self):
        for every, name, fn in self.hooks:
            if self._ping_count % every != 0:
                continue
            at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                fn()
                self.last_ticks[name] = {"ok": True, "at": at}
            except Exception as e:
                logger.warning(f"hook {name} failed: {e}")
                self.last_ticks[name] = {"ok": False, "at": at, "error": str(e)[:200]}

    def auto_status(self) -> dict:
        return {"pings": self._ping_count, "hooks": [h[1] for h in self.hooks],
                "ticks": dict(self.last_ticks)}

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        logger.info("Scheduler started")

    def stop(self):
        self.running = False
        logger.info("Scheduler stopped")

    def _loop(self):
        while self.running:
            try:
                self._process_pending()
                self._ping_count += 1
                if self._ping_count % 5 == 0:
                    self._keep_alive()
                if self._ping_count % 60 == 0:
                    self._auto_learn_kb()
                if self._ping_count % 480 == 0:
                    self._govdata_sync()
                if self._ping_count % 30 == 0:
                    self._dump_backup_snapshot()
                if self._ping_count % 1440 == 0:
                    self._daily_backup()
                self._run_hooks()
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
            time.sleep(60)

    def _dump_backup_snapshot(self):
        """定期把 DB 快照寫回 docs/data/db_backup.json，讓 GitHub Action 抓得到
        （否則快照只在部署時更新，兩次部署之間的流量/內容會隨 ephemeral 磁碟消失）。"""
        try:
            from .database import _dump_to_json
            _dump_to_json()
        except Exception as e:
            logger.warning(f"Backup snapshot failed: {e}")

    def _auto_learn_kb(self):
        try:
            from ..services.knowledge_base import auto_learn
            auto_learn()
        except Exception as e:
            logger.warning(f"Auto-learn KB failed: {e}")

    def _govdata_sync(self):
        # 背景執行，避免大檔下載阻塞主迴圈（每 ~8h 觸發一次）
        t = threading.Thread(target=self._govdata_pipeline_job, daemon=True)
        t.start()

    def _govdata_pipeline_job(self):
        try:
            from ..services.govdata import sync_catalog, auto_pipeline
            result = sync_catalog(max_pages=200)
            pipe = auto_pipeline(batch=3)
            logger.info(f"Govdata pipeline: sync={result} auto={pipe}")
        except Exception as e:
            logger.warning(f"Govdata sync failed: {e}")

    def _daily_backup(self):
        try:
            import json
            from datetime import datetime
            from .config import DATA_DIR
            tables = ["contents", "schedules", "analytics", "contacts", "accounts", "ai_templates"]
            data = {}
            for t in tables:
                try:
                    data[t] = fetch(f"SELECT * FROM {t}")
                except Exception:
                    data[t] = []
            now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            backup_path = DATA_DIR / f"backup_{now}.json"
            backup_path.write_text(json.dumps(data, ensure_ascii=False, default=str), encoding="utf-8")
            logger.info(f"Daily backup saved: {backup_path.name}")
        except Exception as e:
            logger.warning(f"Daily backup failed: {e}")

    def _keep_alive(self):
        try:
            urllib.request.urlopen(f"{RENDER_SELF_URL}/api/status", timeout=10)
            logger.debug("Keep-alive ping sent")
        except Exception as e:
            logger.warning(f"Keep-alive ping failed: {e}")

    def _process_pending(self):
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        due = fetch(
            "SELECT s.*, c.title, c.body, c.media_urls "
            "FROM schedules s JOIN contents c ON s.content_id = c.id "
            "WHERE s.status = 'pending' AND s.scheduled_at <= ?",
            [now]
        )
        for item in due:
            self._publish(item)

    def _publish(self, item):
        platform = item["platform"]
        connector = self.connectors.get(platform)
        if not connector:
            execute("UPDATE schedules SET status='failed', error='No connector' WHERE id=?", [item["id"]])
            return

        try:
            media_urls = eval(item.get("media_urls") or "[]")
            result = connector.post(item["body"], media_urls=media_urls)
            execute(
                "UPDATE schedules SET status='done', error=? WHERE id=?",
                [result.get("post_url", ""), item["id"]]
            )
            execute(
                "UPDATE contents SET status='published', published_at=datetime('now') WHERE id=?",
                [item["content_id"]]
            )
            logger.info(f"Published: {item['title']} → {platform}")
        except Exception as e:
            retry = item["retry_count"]
            if retry >= 3:
                execute(
                    "UPDATE schedules SET status='failed', error=?, retry_count=? WHERE id=?",
                    [str(e), retry + 1, item["id"]]
                )
            else:
                execute(
                    "UPDATE schedules SET retry_count=? WHERE id=?",
                    [retry + 1, item["id"]]
                )
            logger.error(f"Publish failed: {item['title']} → {platform}: {e}")

    def schedule_content(self, content_id, platforms, schedule_time):
        for platform in platforms:
            execute(
                "INSERT INTO schedules (content_id, platform, scheduled_at) VALUES (?, ?, ?)",
                [content_id, platform, schedule_time]
            )

    def get_status_summary(self):
        total = fetch("SELECT COUNT(*) as c FROM schedules")[0]["c"]
        pending = fetch("SELECT COUNT(*) as c FROM schedules WHERE status='pending'")[0]["c"]
        done = fetch("SELECT COUNT(*) as c FROM schedules WHERE status='done'")[0]["c"]
        failed = fetch("SELECT COUNT(*) as c FROM schedules WHERE status='failed'")[0]["c"]
        return {"total": total, "pending": pending, "done": done, "failed": failed}
