"""本機維運回滾工具（需 shell 存取，不經公開 API）。

使用範例：
  python marketing_system/scripts/ops_rollback.py site-settings hero_title --list
  python marketing_system/scripts/ops_rollback.py site-settings hero_title
  python marketing_system/scripts/ops_rollback.py admin --email me@example.com --grant
  python marketing_system/scripts/ops_rollback.py db status
  python marketing_system/scripts/ops_rollback.py db dump
  python marketing_system/scripts/ops_rollback.py db restore
  python marketing_system/scripts/ops_rollback.py webhook --url https://example.onrender.com
  python marketing_system/scripts/ops_rollback.py webhook --delete
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from marketing_system.database import (  # noqa: E402
    DATABASE_BACKUP_PATH,
    DATABASE_PATH,
    _dump_to_json,
    _restore_from_backup,
    execute,
    fetch,
    fetch_one,
    init_db,
)


def _print(data):
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def site_settings(args):
    if args.list:
        _print({
            "current": fetch_one("SELECT * FROM site_settings WHERE key=?", (args.key,)),
            "history": fetch(
                "SELECT * FROM site_settings_history WHERE key=? ORDER BY id DESC LIMIT 20",
                (args.key,),
            ),
        })
        return
    if args.history_id is None:
        row = fetch_one(
            "SELECT * FROM site_settings_history WHERE key=? ORDER BY id DESC LIMIT 1", (args.key,)
        )
    else:
        row = fetch_one(
            "SELECT * FROM site_settings_history WHERE key=? AND id=?", (args.key, args.history_id)
        )
    if not row:
        sys.exit("沒有可還原的版本；先用 --list 查看 history")
    current = fetch_one("SELECT value FROM site_settings WHERE key=?", (args.key,))
    if current and current["value"] != row["value"]:
        execute(
            "INSERT INTO site_settings_history(key, value, changed_by) VALUES(?, ?, ?)",
            [args.key, current["value"], args.actor or "local-rollback"],
        )
    execute(
        "UPDATE site_settings SET value=?, updated_at=datetime('now') WHERE key=?",
        [row["value"], args.key],
    )
    _print({"status": "ok", "key": args.key, "restored_value": row["value"]})


def admin(args):
    if not args.email:
        sys.exit("需要 --email")
    if args.grant == args.revoke:
        sys.exit("請指定 --grant 或 --revoke 其中之一")
    user = fetch_one("SELECT id, is_admin FROM users WHERE email=?", (args.email,))
    if not user:
        sys.exit("找不到該使用者")
    action = "grant" if args.grant else "revoke"
    execute("UPDATE users SET is_admin=? WHERE id=?", [1 if args.grant else 0, user["id"]])
    execute(
        "INSERT INTO admin_audit(actor, target, action) VALUES(?, ?, ?)",
        [args.actor or "local-break-glass", args.email, action],
    )
    _print({"status": "ok", "email": args.email, "is_admin": bool(args.grant), "action": action})


def db(args):
    if args.db_action == "status":
        try:
            data = json.loads(DATABASE_BACKUP_PATH.read_text(encoding="utf-8"))
        except Exception as e:
            sys.exit(f"無法讀取 backup：{e}")
        _print({
            "database": str(DATABASE_PATH),
            "backup": str(DATABASE_BACKUP_PATH),
            "backup_rows": {k: len(v) for k, v in data.items()},
        })
    elif args.db_action == "dump":
        if not DATABASE_PATH.exists():
            sys.exit("資料庫不存在，無可備份內容")
        _dump_to_json()
        _print({"status": "ok", "backup": str(DATABASE_BACKUP_PATH)})
    else:
        if not DATABASE_BACKUP_PATH.exists():
            sys.exit("找不到 backup JSON，無法還原")
        init_db()
        _restore_from_backup()
        _print({"status": "ok", "restored_from": str(DATABASE_BACKUP_PATH)})


def webhook(args):
    token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN", "")
    if not token:
        sys.exit("請先設定 TELEGRAM_BOT_TOKEN 或 TELEGRAM_TOKEN")
    secret = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
    url = f"https://api.telegram.org/bot{token}/"
    if args.delete:
        payload = {"url": ""}
        action = "deleteWebhook"
    else:
        if not args.url:
            sys.exit("需要 --url 或 --delete")
        if not secret:
            sys.exit("設定 TELEGRAM_WEBHOOK_SECRET 後再註冊 webhook（失敗關閉政策）")
        payload = {
            "url": args.url.rstrip("/") + "/api/telegram/webhook",
            "secret_token": secret,
            "allowed_updates": ["message", "channel_post"],
        }
        action = "setWebhook"
    import requests
    resp = requests.post(url + action, json=payload, timeout=15)
    _print(resp.json())


def main():
    parser = argparse.ArgumentParser(description="本機維運回滾工具")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("site-settings", help="還原後台設定值")
    p.add_argument("key")
    p.add_argument("--history-id", type=int)
    p.add_argument("--list", action="store_true")
    p.add_argument("--actor", default="")
    p.set_defaults(func=site_settings)

    p = sub.add_parser("admin", help="break-glass 修復管理員權限（繞過 API）")
    p.add_argument("--email")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--grant", action="store_true")
    g.add_argument("--revoke", action="store_true")
    p.add_argument("--actor", default="")
    p.set_defaults(func=admin)

    p = sub.add_parser("db", help="資料庫備份／還原")
    p.add_argument("db_action", choices=["status", "dump", "restore"])
    p.set_defaults(func=db)

    p = sub.add_parser("webhook", help="重新註冊或移除 Telegram webhook")
    p.add_argument("--url")
    p.add_argument("--delete", action="store_true")
    p.set_defaults(func=webhook)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
