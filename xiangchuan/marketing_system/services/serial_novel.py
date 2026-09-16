"""AI 連載小說引擎 — 每天自動續寫一章，讓網站有不論時間都在更新的內容磁鐵。

續寫邏輯：
- 每部小說把「前 3 章 + 最近一章摘要」餵給 GROQ，請它寫下一章
- 章與章之間用「摘要」維持連續性（避免 token 爆量）
- 一天至多產一章（用 next_available_at 控速），避免燒 API 額度
"""
import logging
from ..config import GROQ_API_KEY, GROQ_MODEL
from ..database import fetch, fetch_one, execute

logger = logging.getLogger(__name__)

FREE_CHAPTERS = 5  # 免費讀 5 章，之後需 Pro（兌換開通碼）


class SerialNovelEngine:
    def __init__(self):
        import groq
        self.client = None
        if GROQ_API_KEY:
            try:
                from groq import Groq
                self.client = Groq(api_key=GROQ_API_KEY)
            except Exception as e:
                logger.warning(f"Groq init failed: {e}")

    def is_available(self):
        return self.client is not None

    def list_novels(self):
        rows = fetch(
            "SELECT id, title, summary, genre, status, chapter_count, next_available_at "
            "FROM novels ORDER BY created_at DESC"
        )
        for r in rows:
            last = fetch_one("SELECT title FROM novel_chapters WHERE novel_id=? ORDER BY chapter_no DESC LIMIT 1", (r["id"],))
            r["latest_chapter_title"] = last["title"] if last else ""
        return rows

    def get_novel(self, novel_id: int):
        n = fetch_one("SELECT * FROM novels WHERE id=?", (novel_id,))
        if not n:
            return None
        chapters = fetch(
            "SELECT id, novel_id, chapter_no, title, created_at FROM novel_chapters WHERE novel_id=? ORDER BY chapter_no ASC",
            (novel_id,),
        )
        n["chapters"] = chapters
        return n

    def get_chapter(self, novel_id: int, chapter_no: int):
        return fetch_one(
            "SELECT * FROM novel_chapters WHERE novel_id=? AND chapter_no=?",
            (novel_id, chapter_no),
        )

    def _last_summary(self, novel_id: int, chapter_no: int, tail: int = 3) -> str:
        """取該章之前最多 tail 章做摘要。抓全文最後 800 字維持連續性。"""
        rows = fetch(
            "SELECT chapter_no, title, body FROM novel_chapters WHERE novel_id=? AND chapter_no<? ORDER BY chapter_no DESC LIMIT ?",
            (novel_id, chapter_no, tail),
        )
        parts = []
        for r in reversed(rows):
            body = (r["body"] or "")
            snippet = body[-700:] if len(body) > 700 else body
            parts.append(f"第{r['chapter_no']}章《{r['title']}》結尾：{snippet}")
        return "\n\n".join(parts)

    def continue_novel(self, novel: dict, chapter_no: int):
        """產生第一章（開局）或其後的第 chapter_no 章。回傳 (title, body)。"""
        if chapter_no == 1:
            prompt = f"""你是網路小說作家。請為一部新連載小說寫「第一章」，要求：

題目：《{novel['title']}》
類型：{novel['genre']}
簡介：{novel['summary']}

第一章要完成的任務：
1. 開頭 3 句立刻製造鉤子（衝突、反轉或奇遇）
2. 建立主角與當下處境
3. 結尾停在一個「非看下回不可」的懸念

文風：繁體中文、章節約 1200~1600 字、節奏明快、有畫面感。
只輸出小說正文，不要輸出標題或說明文字。"""
        else:
            last = "".join(self._last_summary(novel["id"], chapter_no))
            prompt = f"""你是網路小說作家。這是《{novel['title']}》（{novel['genre']}）的第 {chapter_no} 章。

上一章結尾內容（供連續性參考）：
{last}

請寫出第 {chapter_no} 章：
- 承接上文情節，逐步推進主線，製造新的轉折或反轉
- 讓追讀的讀者有「有進展」與「想繼續看」的感覺
- 章節結尾停在一個懸念

文風：繁體中文、章節約 1200~1600 字、節奏明快、有畫面感。
只輸出小說正文，不要輸出標題或說明文字。"""
        try:
            resp = self.client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8,
                max_tokens=2400,
            )
            body = (resp.choices[0].message.content or "").strip()
            return self._extract_title(body), self._strip_title(body)
        except Exception as e:
            logger.error(f"GROQ novel continue failed: {e}")
            return "第N章", f"⚠️ AI 續寫失敗（{e}），請稍後再試。"

    def _extract_title(self, body: str):
        line = body.splitlines()[0].strip()[:40]
        if line and len(line) < 30:
            return line.strip("【】[]（）() \t:")
        return f"第 {self._current} 章" if False else "（續）"

    def _strip_title(self, body: str):
        lines = body.splitlines()
        if lines and len(lines[0].strip()) < 30 and lines[0].strip():
            lines = lines[1:]
        return "\n".join(lines).strip()

    def ensure_chapter(self, novel_id: int, chapter_no: int = None):
        """確保指定章節存在；若不存在且符合時序，就呼叫 AI 續寫。
        預設 chapter_no=None 表示「下一章」（今天的最新一集）。
        回傳 (chapter, is_new)。"""
        import time
        novel = fetch_one("SELECT * FROM novels WHERE id=?", (novel_id,))
        if not novel:
            return None, False

        if chapter_no is None:
            chapter_no = novel["chapter_count"] + 1

        existing = self.get_chapter(novel_id, chapter_no)
        if existing:
            return existing, False

        if not self.is_available():
            return None, False

        # 每日限速：只有在當天還沒產出新章時才續寫（chapter_no 超過既有章節數）
        last_row = fetch_one(
            "SELECT created_at FROM novel_chapters WHERE novel_id=? ORDER BY chapter_no DESC LIMIT 1",
            (novel_id,),
        )
        now = time.strftime("%Y-%m-%d")
        if last_row and last_row["created_at"] >= now and chapter_no >= novel["chapter_count"] + 1:
            # 今天已產過新章，直接回最新章
            cur = self.get_chapter(novel_id, novel["chapter_count"])
            return cur, False

        title, body = self.continue_novel(novel, chapter_no)
        try:
            execute(
                "INSERT INTO novel_chapters (novel_id, chapter_no, title, body) VALUES (?,?,?,?)",
                (novel_id, chapter_no, title, body),
            )
            execute(
                "UPDATE novels SET chapter_count=?, next_available_at=datetime('now', '+1 day') WHERE id=?",
                (chapter_no, novel_id),
            )
            chap = self.get_chapter(novel_id, chapter_no)
            return chap, True
        except Exception as e:
            logger.error(f"novel chapter insert failed: {e}")
            return None, False

    def create_novel(self, title: str, summary: str, genre: str):
        """建立新小說並當場生成第二章（第一二章用戶瀏覽時才會生成，避免開書卻無人看）。"""
        try:
            cid = execute(
                "INSERT INTO novels (title, summary, genre, status) VALUES (?,?,?, 'serializing')",
                (title, summary, genre),
            )
            return cid
        except Exception as e:
            logger.error(f"create novel failed: {e}")
            return None


def free_chapter_limit():
    return FREE_CHAPTERS