import logging
import json
import time
from pathlib import Path
from .base import PlatformConnector
from ..config import BROWSER_HEADLESS, BROWSER_TIMEOUT, DATA_DIR

logger = logging.getLogger(__name__)


class BrowserAutomation(PlatformConnector):
    def __init__(self, config=None):
        super().__init__(config)
        self.context = None
        self.browser = None
        self.playwright = None

    async def _ensure_browser(self):
        if self.browser:
            return
        from playwright.async_api import async_playwright
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=BROWSER_HEADLESS)

    async def _close_browser(self):
        if self.browser:
            await self.browser.close()
            self.browser = None
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None


class ThreadsConnector(BrowserAutomation):
    def __init__(self, config=None):
        super().__init__(config)
        self.name = "threads"
        self.username = config.get("username", "")
        self.password = config.get("password", "")

    def verify(self):
        return bool(self.username and self.password)

    def post(self, text, media_urls=None):
        import asyncio
        return asyncio.run(self._async_post(text, media_urls))

    async def _async_post(self, text, media_urls=None):
        await self._ensure_browser()
        auth_path = DATA_DIR / "threads_auth.json"
        context_opts = {"storage_state": str(auth_path)} if auth_path.exists() else {}
        context = await self.browser.new_context(**context_opts)
        page = await context.new_page()

        try:
            await page.goto("https://www.threads.com/login", timeout=BROWSER_TIMEOUT)
            if "login" in page.url or "/accounts/login" in page.url:
                # Threads 2026：輸入框用 placeholder 識別，非 name 欄位
                await page.locator("input[type='text']").first.fill(self.username)
                await page.locator("input[type='password']").first.fill(self.password)
                # 登入按鈕可能是 <button> 或 <input type=submit>
                submit = page.locator("div[role='button']:has-text('Log in')")
                if await submit.count():
                    await submit.first.click()
                else:
                    await page.locator("input[type='submit'], button[type='submit']").first.click()
                await page.wait_for_timeout(6000)
                if "login" in page.url:
                    raise Exception("登入失敗：請確認帳號密碼（可能觸發驗證碼或 2FA）")
                try:
                    await context.storage_state(path=str(auth_path))
                except Exception:
                    pass

            await page.goto("https://www.threads.com", timeout=BROWSER_TIMEOUT)
            await page.wait_for_timeout(4000)
            # Threads compose：一個 (或最近) 的 contenteditable 文字框
            tb = page.locator("div[contenteditable='true'], div[role='textbox']").first
            await tb.click()
            await tb.fill(self.truncate(text, 500))
            await page.wait_for_timeout(1500)
            # 貼文按鈕：找含 Post 文字的 button
            btn = page.locator("button:has-text('Post')").last
            await btn.click()
            await page.wait_for_timeout(3000)
            return {"success": True, "post_url": "https://www.threads.com/"}

        except Exception as e:
            raise Exception(f"Threads post failed: {e}")
        finally:
            await context.close()


class DcardConnector(BrowserAutomation):
    def __init__(self, config=None):
        super().__init__(config)
        self.name = "dcard"
        self.email = config.get("email", "")
        self.password = config.get("password", "")

    def verify(self):
        return bool(self.email and self.password)

    def post(self, text, media_urls=None):
        import asyncio
        return asyncio.run(self._async_post(text, media_urls))

    async def _async_post(self, text, media_urls=None):
        await self._ensure_browser()
        context = await self.browser.new_context(storage_state=str(DATA_DIR / "dcard_auth.json"))
        page = await context.new_page()

        try:
            await page.goto("https://www.dcard.tw/", timeout=BROWSER_TIMEOUT)
            login_btn = page.locator("a:has-text('登入')")
            if await login_btn.is_visible():
                await login_btn.click()
                await page.wait_for_timeout(2000)
                email_input = page.locator("input[type='email']")
                if await email_input.is_visible():
                    await email_input.fill(self.email)
                    await page.fill("input[type='password']", self.password)
                    await page.click("button:has-text('登入')")
                    await page.wait_for_timeout(5000)
                    await context.storage_state(path=str(DATA_DIR / "dcard_auth.json"))

            parts = text.split("\n\n", 1)
            title = parts[0].replace("#", "").strip()[:100]
            body = parts[1] if len(parts) > 1 else text

            await page.goto("https://www.dcard.tw/f/trending", timeout=BROWSER_TIMEOUT)
            await page.click("button:has-text('發表文章')")
            await page.wait_for_timeout(2000)

            title_input = page.locator("div[contenteditable='true']").first
            await title_input.fill(title)
            body_input = page.locator("div[contenteditable='true']").last
            await body_input.fill(body)
            await page.click("button:has-text('發佈')")
            await page.wait_for_timeout(3000)
            return {"success": True, "post_url": "https://www.dcard.tw/"}

        except Exception as e:
            raise Exception(f"Dcard post failed: {e}")
        finally:
            await context.close()


class XiaohongshuConnector(BrowserAutomation):
    def __init__(self, config=None):
        super().__init__(config)
        self.name = "xiaohongshu"
        self.phone = config.get("phone", "")
        self.password = config.get("password", "")

    def verify(self):
        return bool(self.phone and self.password)

    def post(self, text, media_urls=None):
        import asyncio
        return asyncio.run(self._async_post(text, media_urls))

    async def _async_post(self, text, media_urls=None):
        await self._ensure_browser()
        context = await self.browser.new_context(storage_state=str(DATA_DIR / "xhs_auth.json"))
        page = await context.new_page()

        try:
            await page.goto("https://www.xiaohongshu.com/explore", timeout=BROWSER_TIMEOUT)
            login_btn = page.locator("a:has-text('登录')")
            if await login_btn.is_visible():
                await login_btn.click()
                await page.wait_for_timeout(2000)
                phone_input = page.locator("input[placeholder*='手机']")
                if await phone_input.is_visible():
                    await phone_input.fill(self.phone)
                    await page.fill("input[type='password']", self.password)
                    await page.click("button:has-text('登录')")
                    await page.wait_for_timeout(5000)
                    await context.storage_state(path=str(DATA_DIR / "xhs_auth.json"))

            await page.goto("https://www.xiaohongshu.com/explore", timeout=BROWSER_TIMEOUT)
            await page.click("a:has-text('发布')")
            await page.wait_for_timeout(3000)
            title_input = page.locator("div[placeholder='标题']")
            await title_input.fill(text[:100])
            body = page.locator("div[placeholder='正文']")
            await body.fill(text)
            await page.click("button:has-text('发布')")
            await page.wait_for_timeout(3000)
            return {"success": True, "post_url": "https://www.xiaohongshu.com/"}

        except Exception as e:
            raise Exception(f"Xiaohongshu post failed: {e}")
        finally:
            await context.close()
