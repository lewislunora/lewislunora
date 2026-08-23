#!/usr/bin/env python3
"""
翔川 Neo｜自動安全掃描器
只掃描自己的網站 lewislunora.onrender.com
用法: python3 security_scanner.py [--url URL] [--telegram]
"""

import ssl
import json
import sys
import os
import requests
import socket
from datetime import datetime
from urllib.parse import urlparse

# ============================
# 設定
# ============================
DEFAULT_TARGET = "https://lewislunora.onrender.com"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# 安全 Headers 檢查清單（OWASP 建議）
SECURITY_HEADERS = {
    "Strict-Transport-Security": {
        "required": True,
        "description": "強制 HTTPS",
        "severity": "HIGH",
        "fix": "加入 HSTS header: Strict-Transport-Security: max-age=31536000; includeSubDomains"
    },
    "Content-Security-Policy": {
        "required": True,
        "description": "防止 XSS 與資料注入",
        "severity": "HIGH",
        "fix": "設定 CSP policy，限制 script-src、style-src 等"
    },
    "X-Frame-Options": {
        "required": True,
        "description": "防止點擊劫持",
        "severity": "MEDIUM",
        "fix": "加入 X-Frame-Options: DENY 或 SAMEORIGIN"
    },
    "X-Content-Type-Options": {
        "required": True,
        "description": "防止 MIME 類型嗅探",
        "severity": "LOW",
        "fix": "加入 X-Content-Type-Options: nosniff"
    },
    "X-XSS-Protection": {
        "required": False,
        "description": "舊版瀏覽器 XSS 保護（已棄用但仍有價值）",
        "severity": "INFO",
        "fix": "加入 X-XSS-Protection: 1; mode=block"
    },
    "Referrer-Policy": {
        "required": True,
        "description": "控制 referer 資訊洩漏",
        "severity": "MEDIUM",
        "fix": "加入 Referrer-Policy: strict-origin-when-cross-origin"
    },
    "Permissions-Policy": {
        "required": False,
        "description": "控制瀏覽器功能存取",
        "severity": "LOW",
        "fix": "設定 Permissions-Policy 限制 camera、microphone 等"
    },
    "Cross-Origin-Opener-Policy": {
        "required": False,
        "description": "隔離瀏覽上下文",
        "severity": "INFO",
        "fix": "加入 Cross-Origin-Opener-Policy: same-origin"
    },
    "Cross-Origin-Resource-Policy": {
        "required": False,
        "description": "控制跨源資源存取",
        "severity": "INFO",
        "fix": "加入 Cross-Origin-Resource-Policy: same-origin"
    },
}

# 危險的 Response Headers（不應該出現）
DANGEROUS_HEADERS = [
    "Server",           # 泄漏伺服器版本
    "X-Powered-By",     # 泄漏技術棧
    "X-AspNet-Version", # 泄漏 ASP.NET 版本
    "X-AspNetMvc-Version",
]

# 已知的敏感路徑
SENSITIVE_PATHS = [
    "/.env",
    "/.git/config",
    "/.git/HEAD",
    "/wp-admin/",
    "/phpmyadmin/",
    "/admin/",
    "/api/admin",
    "/api/debug",
    "/api/env",
    "/server-status",
    "/server-info",
    "/.htaccess",
    "/web.config",
    "/robots.txt",       # 檢查是否洩漏敏感路徑
    "/sitemap.xml",
    "/.well-known/security.txt",
    "/swagger.json",
    "/openapi.json",
    "/docs",
    "/redoc",
]


class SecurityScanner:
    def __init__(self, target_url):
        self.target = target_url.rstrip("/")
        self.parsed = urlparse(self.target)
        self.domain = self.parsed.hostname
        self.findings = []
        self.info = []

    def add_finding(self, severity, title, detail, fix=""):
        self.findings.append({
            "severity": severity,
            "title": title,
            "detail": detail,
            "fix": fix,
        })

    def add_info(self, title, detail):
        self.info.append({"title": title, "detail": detail})

    # ============================
    # 1. HTTP Security Headers
    # ============================
    def check_headers(self):
        try:
            resp = requests.get(self.target, timeout=15, allow_redirects=True)
            headers = {k.lower(): v for k, v in resp.headers.items()}

            # 檢查必要 headers
            for header, config in SECURITY_HEADERS.items():
                h_lower = header.lower()
                if h_lower in headers:
                    value = headers[h_lower]
                    self.add_info(f"✅ {header}", value[:100])
                elif config["required"]:
                    self.add_finding(
                        config["severity"],
                        f"缺少安全 Header: {header}",
                        config["description"],
                        config["fix"]
                    )

            # 檢查危險 headers
            for header in DANGEROUS_HEADERS:
                h_lower = header.lower()
                if h_lower in headers:
                    self.add_finding(
                        "MEDIUM",
                        f"洩漏伺服器資訊: {header}",
                        f"值: {headers[h_lower]}",
                        f"移除 {header} header 或設為空值"
                    )

            # 檢查 HTTPS 強制跳轉
            if resp.url.startswith("http://"):
                self.add_finding(
                    "HIGH",
                    "未強制 HTTPS",
                    f"HTTP 請求未跳轉到 HTTPS，當前 URL: {resp.url}",
                    "設定 HTTP → HTTPS 強制跳轉"
                )

            # 檢查 Cookie 安全
            for cookie in resp.cookies:
                issues = []
                if not cookie.secure:
                    issues.append("缺少 Secure flag")
                if not cookie.has_nonstandard_attr("HttpOnly"):
                    issues.append("缺少 HttpOnly flag")
                if "SameSite" not in str(cookie):
                    issues.append("缺少 SameSite attribute")
                if issues:
                    self.add_finding(
                        "MEDIUM",
                        f"Cookie 安全問題: {cookie.name}",
                        ", ".join(issues),
                        "設定 Cookie: Secure; HttpOnly; SameSite=Strict"
                    )

            self.add_info("HTTP 狀態碼", f"{resp.status_code}")
            self.add_info("最終 URL", resp.url)
            self.add_info("回應時間", f"{resp.elapsed.total_seconds():.2f}s")

        except requests.exceptions.RequestException as e:
            self.add_finding("CRITICAL", "無法連線到目標", str(e), "確認目標是否在線")

    # ============================
    # 2. SSL/TLS 配置
    # ============================
    def check_ssl(self):
        if self.parsed.scheme != "https":
            self.add_finding("CRITICAL", "未使用 HTTPS", "目標不支援 HTTPS", "設定 SSL 憑證")
            return

        try:
            ctx = ssl.create_default_context()
            with ctx.wrap_socket(socket.socket(), server_hostname=self.domain) as s:
                s.settimeout(10)
                s.connect((self.domain, 443))
                cert = s.getpeercert()
                cipher = s.cipher()
                version = s.version()

                # 憑證有效期
                not_after = ssl.cert_time_to_seconds(cert["notAfter"])
                days_left = (not_after - datetime.now().timestamp()) / 86400
                if days_left < 30:
                    self.add_finding(
                        "HIGH",
                        "SSL 憑證即將過期",
                        f"剩餘 {int(days_left)} 天",
                        "設定自動續期（Let's Encrypt + certbot）"
                    )
                elif days_left < 90:
                    self.add_finding("MEDIUM", "SSL 憑證 90 天內過期", f"剩餘 {int(days_left)} 天", "安排續期")

                self.add_info("SSL 版本", version)
                self.add_info("加密套件", cipher[0] if cipher else "未知")
                self.add_info("憑證到期", cert["notAfter"])
                self.add_info("憑證發行者", dict(x[0] for x in cert.get("issuer", [])).get("organizationName", "未知"))

                # 檢查憑證鏈
                if len(cert.get("subjectAltName", [])) > 0:
                    domains = [v for t, v in cert["subjectAltName"] if t == "DNS"]
                    self.add_info("憑證涵蓋域名", ", ".join(domains[:5]))

        except ssl.SSLCertVerificationError as e:
            self.add_finding("CRITICAL", "SSL 憑證驗證失敗", str(e), "修復憑證或使用 Let's Encrypt")
        except Exception as e:
            self.add_finding("HIGH", "SSL 連線失敗", str(e), "檢查 SSL 配置")

    # ============================
    # 3. 敏感路徑掃描
    # ============================
    def check_sensitive_paths(self):
        exposed = []
        for path in SENSITIVE_PATHS:
            try:
                url = f"{self.target}{path}"
                resp = requests.get(url, timeout=10, allow_redirects=False)
                if resp.status_code == 200:
                    # 確認不是自訂 404 頁面
                    content_type = resp.headers.get("content-type", "")
                    if "text/html" in content_type and len(resp.text) > 500:
                        continue  # 可能是自訂頁面，跳過
                    exposed.append((path, resp.status_code))
            except requests.exceptions.RequestException:
                continue

        if exposed:
            paths_list = "\n".join(f"  {p} → {c}" for p, c in exposed)
            self.add_finding(
                "MEDIUM",
                f"發現 {len(exposed)} 個可能暴露的路徑",
                paths_list,
                "封鎖或限制存取這些路徑"
            )
        else:
            self.add_info("敏感路徑掃描", "未發現暴露的敏感路徑")

    # ============================
    # 4. API 端點探索
    # ============================
    def check_api_endpoints(self):
        api_paths = [
            "/api/status",
            "/api/accounts",
            "/api/contents",
            "/api/schedules",
            "/api/auth/me",
            "/api/docs",
            "/api/openapi.json",
        ]
        accessible = []
        for path in api_paths:
            try:
                url = f"{self.target}{path}"
                resp = requests.get(url, timeout=10, allow_redirects=False)
                if resp.status_code in (200, 401, 403):
                    accessible.append((path, resp.status_code))
            except requests.exceptions.RequestException:
                continue

        if accessible:
            self.add_info(
                f"API 端點回應 ({len(accessible)} 個)",
                "\n".join(f"  {p} → {c}" for p, c in accessible)
            )
            # 檢查是否有未授權可存取的端點
            for path, code in accessible:
                if code == 200 and "/api/accounts" in path:
                    # 檢查是否洩漏 credentials
                    try:
                        r = requests.get(f"{self.target}{path}", timeout=10)
                        items = r.json().get("items", [])
                        creds_exposed = any(
                            item.get("credentials") not in (None, "", "***")
                            for item in items
                        )
                        if creds_exposed:
                            self.add_finding(
                                "HIGH",
                                f"API 未授權存取: {path}",
                                "未登入即可存取帳號 credentials",
                                "確認所有敏感 API 都有認證保護"
                            )
                    except Exception:
                        pass

    # ============================
    # 5. 資訊洩漏檢查
    # ============================
    def check_info_disclosure(self):
        try:
            # 檢查首頁是否洩漏技術資訊
            resp = requests.get(self.target, timeout=10)
            content = resp.text.lower()

            leaks = []
            if "powered-by" in content or "x-powered-by" in content:
                leaks.append("powered-by 標籤")
            if "python" in content and ("flask" in content or "django" in content):
                leaks.append("Python 框架名稱")
            if "sqlite" in content:
                leaks.append("SQLite 資料庫")
            if "fastapi" in content:
                leaks.append("FastAPI 框架")
            if "render.com" in content:
                leaks.append("Render 部署平台")

            if leaks:
                self.add_finding(
                    "LOW",
                    "首頁洩漏技術資訊",
                    "偵測到: " + ", ".join(leaks),
                    "移除頁面上的技術棧標註"
                )
        except requests.exceptions.RequestException:
            pass

    # ============================
    # 執行完整掃描
    # ============================
    def run_full_scan(self):
        print(f"\n🔒 安全掃描開始: {self.target}")
        print(f"   時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        self.check_headers()
        print("  ✓ HTTP Security Headers 檢查完成")

        self.check_ssl()
        print("  ✓ SSL/TLS 配置檢查完成")

        self.check_sensitive_paths()
        print("  ✓ 敏感路徑掃描完成")

        self.check_api_endpoints()
        print("  ✓ API 端點探索完成")

        self.check_info_disclosure()
        print("  ✓ 資訊洩漏檢查完成")

        return self.generate_report()

    # ============================
    # 產生報告
    # ============================
    def generate_report(self):
        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
        self.findings.sort(key=lambda x: severity_order.get(x["severity"], 5))

        counts = {}
        for f in self.findings:
            s = f["severity"]
            counts[s] = counts.get(s, 0) + 1

        severity_emoji = {
            "CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🔵", "INFO": "⚪"
        }

        # 風險等級
        if counts.get("CRITICAL", 0) > 0:
            risk = "🔴 嚴重"
        elif counts.get("HIGH", 0) > 0:
            risk = "🟠 高"
        elif counts.get("MEDIUM", 0) > 0:
            risk = "🟡 中等"
        else:
            risk = "🟢 低"

        report = {
            "target": self.target,
            "scan_time": datetime.now().isoformat(),
            "risk_level": risk,
            "counts": counts,
            "findings": self.findings,
            "info": self.info,
        }

        # 印出摘要
        print(f"\n{'='*60}")
        print(f"🔒 安全掃描報告摘要")
        print(f"{'='*60}")
        print(f"目標: {self.target}")
        print(f"時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"風險等級: {risk}")
        print(f"\n漏洞統計:")
        for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]:
            if counts.get(sev, 0) > 0:
                print(f"  {severity_emoji[sev]} {sev}: {counts[sev]}")
        print(f"\n總計: {len(self.findings)} 個發現, {len(self.info)} 項資訊")

        if self.findings:
            print(f"\n{'='*60}")
            print(f"漏洞詳情")
            print(f"{'='*60}")
            for i, f in enumerate(self.findings, 1):
                emoji = severity_emoji.get(f["severity"], "⚪")
                print(f"\n{emoji} [{f['severity']}] {f['title']}")
                print(f"   {f['detail'][:200]}")
                if f["fix"]:
                    print(f"   💡 修復: {f['fix'][:150]}")

        return report

    # ============================
    # 推播到 Telegram
    # ============================
    def push_telegram(self, report):
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            print("\n⚠️  未設定 TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID，跳過推播")
            return False

        counts = report["counts"]
        severity_emoji = {
            "CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🔵", "INFO": "⚪"
        }

        msg = f"🔒 安全掃描完成\n"
        msg += f"目標: {report['target']}\n"
        msg += f"風險等級: {report['risk_level']}\n\n"
        msg += "漏洞統計:\n"
        for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]:
            c = counts.get(sev, 0)
            if c > 0:
                msg += f"  {severity_emoji[sev]} {sev}: {c}\n"
        msg += f"\n總計: {len(report['findings'])} 個發現"

        if report["findings"]:
            msg += "\n\n最嚴重的 3 個問題:\n"
            for f in report["findings"][:3]:
                emoji = severity_emoji.get(f["severity"], "⚪")
                msg += f"{emoji} {f['title']}\n"

        try:
            requests.post(
                "https://api.telegram.org/bot" + TELEGRAM_BOT_TOKEN + "/sendMessage",
                json={"chat_id": TELEGRAM_CHAT_ID, "text": msg},
                timeout=10,
            )
            print("\n✅ Telegram 推播成功")
            return True
        except Exception as e:
            print(f"\n❌ Telegram 推播失敗: {e}")
            return False


def main():
    import argparse
    parser = argparse.ArgumentParser(description="翔川 Neo 自動安全掃描器")
    parser.add_argument("--url", default=DEFAULT_TARGET, help="掃描目標 URL")
    parser.add_argument("--telegram", action="store_true", help="推播結果到 Telegram")
    parser.add_argument("--json", help="輸出 JSON 報告到指定路徑")
    args = parser.parse_args()

    scanner = SecurityScanner(args.url)
    report = scanner.run_full_scan()

    if args.telegram:
        scanner.push_telegram(report)

    if args.json:
        with open(args.json, "w") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n📄 JSON 報告已輸出: {args.json}")


if __name__ == "__main__":
    main()
