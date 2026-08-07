import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)


def get_smtp_config():
    return {
        "host": os.getenv("SMTP_HOST", "smtp.gmail.com"),
        "port": int(os.getenv("SMTP_PORT", "587")),
        "user": os.getenv("SMTP_USER", ""),
        "password": os.getenv("SMTP_PASS", ""),
        "to": os.getenv("CONTACT_TO", "lewislunora@gmail.com"),
    }


def is_configured():
    cfg = get_smtp_config()
    return bool(cfg["user"] and cfg["password"])


def send_contact_email(data: dict) -> dict:
    cfg = get_smtp_config()
    if not is_configured():
        return _fallback_log(data)

    subject = "🔔 新預約諮詢 - 翔川 Neo AI"
    body_parts = []
    field_labels = {
        "姓名": "姓名",
        "公司": "公司/店家",
        "聯絡方式": "Line ID / 手機",
        "Email": "Email",
        "行業別": "行業別",
        "備註": "想了解的服務",
    }
    for key, label in field_labels.items():
        val = data.get(key, "").strip()
        if val:
            body_parts.append(f"{label}：{val}")

    body = "\n".join(body_parts) if body_parts else "(空表單)"

    msg = MIMEMultipart()
    msg["From"] = cfg["user"]
    msg["To"] = cfg["to"]
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=10) as server:
            server.starttls()
            server.login(cfg["user"], cfg["password"])
            server.send_message(msg)
        logger.info(f"Contact email sent to {cfg['to']}")
        return {"status": "sent"}
    except Exception as e:
        logger.error(f"SMTP failed: {e}")
        return _fallback_log(data, str(e))


def _fallback_log(data: dict, error: str = None):
    logger.warning(f"Contact form fallback (SMTP not configured or failed): {data}")
    return {"status": "logged", "note": "Form submitted (email not sent)", "error": error}


def send_generic_email(subject: str, text: str) -> dict:
    cfg = get_smtp_config()
    if not is_configured():
        logger.info("SMTP not configured, skipping generic email")
        return {"status": "skipped"}
    msg = MIMEMultipart()
    msg["From"] = cfg["user"]
    msg["To"] = cfg["to"]
    msg["Subject"] = subject
    msg.attach(MIMEText(text, "plain", "utf-8"))
    try:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=10) as server:
            server.starttls()
            server.login(cfg["user"], cfg["password"])
            server.send_message(msg)
        logger.info(f"Generic email sent to {cfg['to']}: {subject}")
        return {"status": "sent"}
    except Exception as e:
        logger.error(f"Generic email SMTP failed: {e}")
        return {"status": "error", "error": str(e)}
