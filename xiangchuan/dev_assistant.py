#!/usr/bin/env python3
"""
🤖 開發助理 Telegram Bot
本地執行，透過 TG 遠端控制開發流程
支援 AI 對話 proxy 到 Render API
"""

import os, sys, subprocess, json, time, logging, shutil, signal
from pathlib import Path
from datetime import datetime
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("devbot")

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8653211794:AAG08xDDj0UDkX18TE60BQSVs-bwwVh8AH8")
ALLOWED_USERS = os.environ.get("DEV_BOT_USERS", "626453598").split(",")
RENDER_API = os.environ.get("RENDER_API_URL", "https://lewislunora.onrender.com")
PROJECT_DIR = Path(__file__).parent.parent
XIANGCHUAN_DIR = PROJECT_DIR / "xiangchuan"
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
POLL_INTERVAL = 3
SERVE_PROCESS = None


def tg_send(chat_id, text):
    for chunk in [text[i:i+4000] for i in range(0, len(text), 4000)]:
        try:
            requests.post(f"{API_URL}/sendMessage", json={"chat_id": chat_id, "text": chunk, "parse_mode": "HTML"}, timeout=10)
        except Exception as e:
            log.error(f"send failed: {e}")


def tg_send_code(chat_id, text):
    safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    tg_send(chat_id, f"<pre>{safe}</pre>")


def is_allowed(chat_id):
    return str(chat_id) in ALLOWED_USERS


def run_cmd(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout, cwd=PROJECT_DIR)
        out = (r.stdout + r.stderr).strip()
        return out or "(no output)"
    except subprocess.TimeoutExpired:
        return "(timeout)"
    except Exception as e:
        return f"Error: {e}"


def cmd_start(chat_id):
    tg_send(chat_id, (
        "🤖 <b>開發助理已上線</b>\n\n"
        "可用指令：\n"
        "/help  — 顯示所有指令\n"
        "/status — Git 狀態 + 站點健康\n"
        "/deploy — Git Push 部署\n"
        "/sites  — 檢查兩站狀態\n"
        "/log    — 最近 Git Log\n"
        "/serve  — 啟動/停止本機伺服器\n"
        "/shell  — 執行 Shell 指令\n"
        "/backup — 備份資料庫\n"
        "/uptime — 系統運行時間\n"
        "/disk   — 磁碟用量\n"
        "/ps     — 程序列表\n"
        "/whoami — 當前使用者"
    ))


def cmd_help(chat_id):
    cmd_start(chat_id)


def cmd_status(chat_id):
    git = run_cmd("git status --short 2>&1")
    branch = run_cmd("git rev-parse --abbrev-ref HEAD 2>&1")
    msg = f"<b>📂 Git 狀態</b>\n分支: {branch}\n\n"
    msg += git if git != "(no output)" else "✅ 乾淨，無未提交變更"
    tg_send_code(chat_id, msg)


def cmd_sites(chat_id):
    sites = {
        "GitHub Pages": "https://lewislunora.github.io/lewislunora/",
        "Render": "https://lewislunora.onrender.com/"
    }
    msg = "<b>🌐 站點狀態</b>\n"
    for name, url in sites.items():
        try:
            r = requests.get(url, timeout=15)
            status = "✅" if r.status_code == 200 else f"⚠️ {r.status_code}"
            msg += f"{status} {name}: {r.status_code}\n"
        except Exception as e:
            msg += f"❌ {name}: {e}\n"
    tg_send(chat_id, msg)


def cmd_deploy(chat_id, msg=""):
    commit_msg = msg.strip() or f"auto: deploy via TG bot"
    tg_send(chat_id, f"🚀 部署中...\n訊息: {commit_msg}")
    log.info(f"Deploy: {commit_msg}")
    out = run_cmd("git add -A")
    out = run_cmd(f"git commit --allow-empty -m '{commit_msg}' 2>&1")
    if "error" in out.lower() and "nothing" not in out.lower():
        tg_send(chat_id, f"⚠️ Commit: {out[:200]}")
    out = run_cmd("git push 2>&1", timeout=60)
    if "error" in out.lower() and "Everything up-to-date" not in out:
        tg_send_code(chat_id, f"❌ Push 失敗:\n{out[:500]}")
    else:
        tg_send(chat_id, "✅ Push 完成，等待部署...")
        time.sleep(5)
        cmd_sites(chat_id)


def cmd_log(chat_id, args=""):
    parts = args.strip().split(maxsplit=1)
    if not args.strip() or parts[0].isdigit():
        n = parts[0] if parts else "10"
        out = run_cmd(f"git log --oneline -{n} 2>&1")
        tg_send_code(chat_id, f"<b>📋 最近 {n} 筆 Commit</b>\n\n{out}")
    elif parts[0] in ("app", "server", "render"):
        log_dir = XIANGCHUAN_DIR / "logs"
        log_file = log_dir / "app.log" if log_dir.exists() else None
        if log_file and log_file.exists():
            lines = run_cmd(f"tail -{parts[1] if len(parts)>1 else 30} {log_file}")
            tg_send_code(chat_id, f"<b>📋 App Log</b>\n\n{lines}")
        else:
            # Try to find any log file
            out = run_cmd("find . -name '*.log' -type f 2>/dev/null | head -10")
            tg_send(chat_id, f"找不到 app.log\n找到的 log 檔:\n{out}")


def cmd_shell(chat_id, cmd):
    if not cmd.strip():
        tg_send(chat_id, "用法: /shell &lt;指令&gt;\n例如: /shell ls -la")
        return
    tg_send(chat_id, f"⚡ $ {cmd}")
    out = run_cmd(cmd, timeout=60)
    tg_send_code(chat_id, out[:3000])


def cmd_serve(chat_id, args=""):
    global SERVE_PROCESS
    action = args.strip().lower()
    if action == "stop":
        if SERVE_PROCESS:
            os.killpg(os.getpgid(SERVE_PROCESS.pid), signal.SIGTERM)
            SERVE_PROCESS = None
            tg_send(chat_id, "🛑 伺服器已停止")
        else:
            tg_send(chat_id, "ℹ️ 沒有運行中的伺服器")
    elif action == "restart":
        cmd_serve(chat_id, "stop")
        time.sleep(1)
        cmd_serve(chat_id, "start")
    else:
        if SERVE_PROCESS:
            tg_send(chat_id, "ℹ️ 伺服器已在運行中")
            return
        try:
            SERVE_PROCESS = subprocess.Popen(
                ["python3", "-m", "uvicorn", "marketing_system.api.server:app", "--host", "0.0.0.0", "--port", "8742"],
                cwd=XIANGCHUAN_DIR, preexec_fn=os.setsid,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            tg_send(chat_id, f"✅ 伺服器已啟動 (PID: {SERVE_PROCESS.pid})")
        except Exception as e:
            tg_send(chat_id, f"❌ 啟動失敗: {e}")


def cmd_backup(chat_id):
    db_path = XIANGCHUAN_DIR / "marketing_system" / "data" / "marketing.db"
    backup_path = XIANGCHUAN_DIR / "data" / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    backup_path.parent.mkdir(exist_ok=True)
    if db_path.exists():
        shutil.copy2(db_path, backup_path)
        size = backup_path.stat().st_size
        tg_send(chat_id, f"✅ 資料庫已備份\n📁 {backup_path.name}\n📦 {size/1024:.1f} KB")
    else:
        tg_send(chat_id, f"ℹ️ 無資料庫檔案於 {db_path}")


def cmd_uptime(chat_id):
    out = run_cmd("uptime")
    tg_send_code(chat_id, f"<b>⏱ 系統運行</b>\n{out}")


def cmd_disk(chat_id):
    out = run_cmd("df -h / | tail -1")
    parts = out.split()
    if len(parts) >= 4:
        tg_send(chat_id, f"<b>💾 磁碟用量</b>\n總計: {parts[1]} / 已用: {parts[2]} / 可用: {parts[3]}")
    else:
        tg_send_code(chat_id, out)


def cmd_ps(chat_id):
    out = run_cmd("ps aux --sort=-%mem | head -15")
    tg_send_code(chat_id, f"<b>🔍 Top 15 程序 (by 記憶體)</b>\n\n{out}")


def cmd_whoami(chat_id):
    out = run_cmd("whoami")
    host = run_cmd("hostname")
    tg_send(chat_id, f"👤 {out} @ {host}")


def cmd_webhook(chat_id, args=""):
    action = args.strip().lower()
    if action == "on":
        url = f"{RENDER_API}/api/telegram/webhook"
        r = requests.post(f"{API_URL}/setWebhook", json={"url": url}, timeout=10)
        tg_send(chat_id, f"✅ Webhook 已設定 → Render\n{r.json()}")
    elif action == "off":
        r = requests.post(f"{API_URL}/deleteWebhook", timeout=10)
        tg_send(chat_id, f"✅ Webhook 已關閉 (Polling 模式)\n{r.json()}")
    else:
        r = requests.get(f"{API_URL}/getWebhookInfo", timeout=10)
        info = r.json().get("result", {})
        tg_send_code(chat_id, json.dumps(info, indent=2, ensure_ascii=False))


def handle_ai_chat(chat_id, text):
    try:
        r = requests.post(f"{RENDER_API}/api/telegram/webhook", json={
            "message": {"chat": {"id": chat_id}, "text": text}
        }, timeout=20)
        if r.status_code == 200:
            log.info(f"AI proxy OK: {text[:50]}")
        else:
            tg_send(chat_id, f"⚠️ AI proxy error: {r.status_code}")
    except Exception as e:
        tg_send(chat_id, f"⚠️ AI proxy failed: {e}")


HANDLERS = {
    "/start": cmd_start, "/help": cmd_help,
    "/status": cmd_status, "/sites": cmd_sites,
    "/backup": cmd_backup,
    "/uptime": cmd_uptime, "/disk": cmd_disk,
    "/ps": cmd_ps, "/whoami": cmd_whoami,
}


def handle_message(chat_id, text):
    if not is_allowed(chat_id):
        tg_send(chat_id, "⛔ 未授權的使用者")
        log.warning(f"Unauthorized access from {chat_id}")
        return

    parts = text.strip().split(maxsplit=1)
    cmd = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    if cmd in ("/log", "/logs"):
        cmd_log(chat_id, "10" if not args else args)
    elif cmd in ("/deploy", "/push"):
        cmd_deploy(chat_id, args)
    elif cmd in ("/webhook", "/wh"):
        cmd_webhook(chat_id, args)
    elif cmd in ("/shell", "/bash", "/sh", "/run"):
        cmd_shell(chat_id, args)
    elif cmd in ("/serve", "/server", "/dev"):
        cmd_serve(chat_id, args)
    elif cmd in HANDLERS:
        HANDLERS[cmd](chat_id)
    else:
        handle_ai_chat(chat_id, text)


def main():
    log.info("🤖 開發助理啟動中...")
    last_offset = 0
    tg_send(ALLOWED_USERS[0], "🤖 <b>開發助理已啟動</b>\n輸入 /help 查看指令")

    while True:
        try:
            r = requests.get(f"{API_URL}/getUpdates", params={
                "offset": last_offset + 1,
                "timeout": 30
            }, timeout=35)
            data = r.json()
            if not data.get("ok"):
                continue
            for update in data["result"]:
                last_offset = update["update_id"]
                msg = update.get("message")
                if not msg:
                    continue
                chat_id = msg["chat"]["id"]
                text = msg.get("text", "")
                if text.startswith("/"):
                    log.info(f"CMD from {chat_id}: {text}")
                    handle_message(chat_id, text)
        except requests.exceptions.Timeout:
            continue
        except Exception as e:
            log.error(f"Poll error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
