import re
import json
import time
import random
import logging
from urllib.parse import urlparse, urljoin
from pathlib import Path

logger = logging.getLogger(__name__)

SEARCH_QUERIES = [
    "AI 自動化 一人公司 推薦",
    "一人公司 工具 2026 省時間",
    "程式碼審查 自動化 AI",
    "工程師 一人創業 心得",
    "AI 客服 免費 推薦",
    "工程師 接案 平台 討論",
    "DevOps 自動化 CI/CD 工具",
    "資料庫 報表 自動化 工具",
    "SaaS 創業 一人 技術",
    "solopreneur 工具 2026 台灣",
]

COMMENT_KEYWORDS = [
    "comment", "reply", "respond", "留言", "回覆", "評論",
    "submit", "post", "發送", "張貼",
]

GUEST_FRIENDLY_SIGNALS = [
    "wordpress-comment", "comment-form", "guest-comment",
    "entry-comments", "comments-area", "comment-wrapper",
    "blog-comment", "article-comment",
]

IGNORE_DOMAINS = [
    "youtube.com", "facebook.com", "instagram.com",
    "twitter.com", "x.com", "linkedin.com", "pinterest.com",
    "tiktok.com", "amazon.com", "shopee",
]

# Direct targets: blogs/forums likely to allow guest comments
TARGET_SITES = [
    "https://www.mobile01.com/forumtopic.php?c=17",
    "https://forum.gamer.com.tw/A.php?bsn=60076",
    "https://www.ptt.cc/",
    "https://blog.trendmicro.com.tw/?p=",
    "https://ithelp.ithome.com.tw/",
    "https://www.playpcesor.com/",
    "https://www.techbang.com/",
]


class WebRoamer:
    def __init__(self, data_dir=None):
        self.seen = set()
        self.data_dir = data_dir or Path("data")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.history_path = self.data_dir / "roam_history.json"
        self._load_history()

    def _load_history(self):
        if self.history_path.exists():
            try:
                self.seen = set(json.loads(self.history_path.read_text()))
            except Exception:
                self.seen = set()

    def _save_history(self):
        try:
            self.history_path.write_text(json.dumps(list(self.seen)))
        except Exception:
            pass

    def _resolve_href(self, href):
        """Decode DDG redirect links to the real URL."""
        if href.startswith("//duckduckgo.com/l/"):
            from urllib.parse import parse_qs
            qs = parse_qs(urlparse(href).query)
            if qs.get("uddg"):
                return qs["uddg"][0]
        return href if href.startswith("http") else None

    def _search_playwright(self, query):
        """Search using real browser (bypasses datacenter IP blocks)."""
        try:
            from playwright.async_api import async_playwright
            import asyncio
            results = []

            async def _run():
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True)
                    page = await browser.new_page(
                        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                                   "Chrome/125.0.0.0 Safari/537.36"
                    )
                    try:
                        await page.goto(
                            "https://duckduckgo.com/?q=" + query,
                            timeout=30000, wait_until="domcontentloaded"
                        )
                        await page.wait_for_timeout(3000)
                        links = await page.eval_on_selector_all(
                            "a[data-testid='result-title-a'], a.result__a",
                            "els => els.map(e => ({href: e.href, text: e.innerText}))"
                        )
                        for item in links:
                            href = item.get("href", "")
                            title = item.get("text", "").strip()
                            if href and title and not any(d in href for d in IGNORE_DOMAINS):
                                parsed = urlparse(href)
                                if parsed.netloc and parsed.netloc not in self.seen:
                                    results.append({"url": href, "title": title, "query": query, "engine": "ddg-browser"})
                                    self.seen.add(parsed.netloc)
                    finally:
                        await browser.close()

            asyncio.run(_run())
            return results
        except Exception as e:
            logger.error(f"Playwright search failed: {e}")
            return []

    def search(self, query=None, max_results=15):
        if not query:
            query = random.choice(SEARCH_QUERIES)
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/125.0.0.0 Safari/537.36"
        }
        results = []
        try:
            import requests
            from lxml import html
            url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}"
            resp = requests.get(url, headers=headers, timeout=15)
            tree = html.fromstring(resp.text)
            for a in tree.xpath("//a[contains(@class,'result__a')]"):
                href = self._resolve_href(a.get("href"))
                title = a.text_content().strip()
                if href and title and not any(d in href for d in IGNORE_DOMAINS):
                    parsed = urlparse(href)
                    if parsed.netloc and parsed.netloc not in self.seen:
                        results.append({"url": href, "title": title, "query": query})
                        self.seen.add(parsed.netloc)
        except Exception as e:
            logger.error(f"DDG search failed: {e}")
        if not results:
            try:
                import requests
                from lxml import html
                url = f"https://www.bing.com/search?q={requests.utils.quote(query)}"
                resp = requests.get(url, headers=headers, timeout=15)
                tree = html.fromstring(resp.text)
                for li in tree.xpath("//li[@class='b_algo']"):
                    a = li.xpath(".//h2/a")[0] if li.xpath(".//h2/a") else None
                    if a is None:
                        continue
                    href = a.get("href")
                    title = a.text_content().strip()
                    if href and title and not any(d in href for d in IGNORE_DOMAINS):
                        parsed = urlparse(href)
                        if parsed.netloc and parsed.netloc not in self.seen:
                            results.append({"url": href, "title": title, "query": query, "engine": "bing"})
                            self.seen.add(parsed.netloc)
            except Exception as e:
                logger.error(f"Bing search failed: {e}")
        # Fallback: real-browser search (bypasses datacenter blocks)
        if not results:
            results = self._search_playwright(query)
        # Last resort: known guest-friendly targets
        if not results:
            for site in TARGET_SITES:
                parsed = urlparse(site)
                if parsed.netloc and parsed.netloc not in self.seen:
                    results.append({"url": site, "title": f"Target: {parsed.netloc}", "query": query, "engine": "direct"})
                    self.seen.add(parsed.netloc)
        self._save_history()
        return results[:max_results]

    def visit(self, url):
        result = {
            "url": url,
            "title": "",
            "content": "",
            "has_comment_form": False,
            "form_selectors": [],
            "guest_friendly": False,
            "error": None,
        }
        try:
            import requests
            from lxml import html
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/125.0.0.0 Safari/537.36"
            }
            resp = requests.get(url, headers=headers, timeout=15)
            tree = html.fromstring(resp.content)
            title_el = tree.xpath("//title")
            result["title"] = title_el[0].text_content().strip() if title_el else ""
            meta_desc = tree.xpath("//meta[@name='description']")
            if meta_desc:
                result["content"] = meta_desc[0].get("content", "")
            if not result["content"]:
                paragraphs = tree.xpath("//p")
                result["content"] = " ".join(p.text_content().strip() for p in paragraphs[:5] if p.text_content().strip())
            result["content"] = result["content"][:2000]
            page_text = resp.text.lower()
            html_str = html.tostring(tree, encoding="unicode").lower()
            for signal in GUEST_FRIENDLY_SIGNALS:
                if signal in html_str:
                    result["guest_friendly"] = True
                    break
            for selector in ["textarea", "input[type=text]", "input[name=comment]", "textarea[name=comment]", "#comment", ".comment-form", "form[action*=comment]"]:
                els = tree.xpath(f"//{selector}" if not selector.startswith(("#", ".")) else f"//*[@id='{selector[1:]}']" if selector.startswith("#") else f"//*[contains(concat(' ', normalize-space(@class), ' '), ' {selector[1:]} ')]")
                if els:
                    result["has_comment_form"] = True
                    result["form_selectors"].append(selector)
            return result
        except Exception as e:
            result["error"] = str(e)
            return result

    def generate_reply(self, page_title, page_content, url, groq_client=None, groq_model=None):
        from ..config import GROQ_API_KEY, GROQ_MODEL
        api_key = groq_client or GROQ_API_KEY
        model = groq_model or GROQ_MODEL
        if not api_key:
            return None
        try:
            from groq import Groq
            client = Groq(api_key=api_key) if isinstance(api_key, str) else groq_client
            prompt = f"""你是一個在網路論壇或部落格上自然分享經驗的專業人士。請根據以下頁面內容，寫一則留言回覆。

頁面標題：{page_title[:200]}
頁面內容摘要：{page_content[:1000]}
頁面網址：{url}

要求：
- 語氣自然，像真人經驗分享，不要像廣告
- 如果文章在問問題，就給具體有用的回答
- 如果文章在分享經驗，就補充相關觀點
- 長度 50-150 字
- 繁體中文
- 結尾自然帶入：「我之前也遇到類似問題，後來用這個方法解決了 → lewislunora.onrender.com/」
- 不要用 hashtag
- 不要提到「AI 生成」或「機器人」"""

            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.7,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Generate reply failed: {e}")
            return None

    async def post_reply_playwright(self, url, reply_text, name="小川"):
        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, timeout=30000, wait_until="domcontentloaded")
                await page.wait_for_timeout(3000)
                textarea = None
                for sel in ["textarea[name=comment]", "textarea#comment", "#comment", "textarea[aria-label*=comment]", "textarea[placeholder*=留言]", "textarea[placeholder*=回覆]", "textarea"]:
                    el = page.locator(sel).first
                    if await el.count():
                        textarea = el
                        break
                if not textarea:
                    await browser.close()
                    return {"ok": False, "error": "找不到留言輸入框"}
                await textarea.fill(reply_text)
                name_input = None
                for sel in ["input[name=author]", "input[name=name]", "input#author", "input#name"]:
                    el = page.locator(sel).first
                    if await el.count():
                        name_input = el
                        break
                if name_input:
                    await name_input.fill(name)
                email_input = page.locator("input[name=email]").first
                if await email_input.count():
                    await email_input.fill("guest@example.com")
                submit_btn = None
                for sel in ["button[type=submit]", "input[type=submit]", "#submit", ".submit", "button:has-text('送出')", "button:has-text('留言')", "button:has-text('發送')", "button:has-text('回覆')"]:
                    el = page.locator(sel).first
                    if await el.count():
                        submit_btn = el
                        break
                if not submit_btn:
                    await browser.close()
                    return {"ok": False, "error": "找不到送出按鈕"}
                await submit_btn.click()
                await page.wait_for_timeout(3000)
                await browser.close()
                return {"ok": True, "url": url}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def roam(self, max_sites=5, groq_client=None, groq_model=None):
        results = []
        query = random.choice(SEARCH_QUERIES)
        sites = self.search(query, max_results=max_sites * 3)
        random.shuffle(sites)
        attempted = 0
        for site in sites[:max_sites * 2]:
            if attempted >= max_sites:
                break
            info = self.visit(site["url"])
            results.append(info)
            attempted += 1
            if info["has_comment_form"] and info["guest_friendly"]:
                reply = self.generate_reply(
                    info["title"], info["content"], info["url"],
                    groq_client, groq_model
                )
                info["generated_reply"] = reply
                if reply:
                    import asyncio
                    post_result = asyncio.run(
                        self.post_reply_playwright(info["url"], reply)
                    )
                    info["post_result"] = post_result
            time.sleep(random.uniform(2, 4))
        return {"query": query, "results": results, "total_found": len(sites)}
