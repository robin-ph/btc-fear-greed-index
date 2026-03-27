"""Binance Square scraper — hardened for daily cron runs."""

import asyncio
from datetime import datetime, timezone
from playwright.async_api import async_playwright

from config.settings import BINANCE_SQUARE_MAX_POSTS, BINANCE_SQUARE_HASHTAGS
from scrapers import ProxyBroken, is_proxy_error


class BinanceSquareScraper:
    def __init__(self):
        self.max_posts = BINANCE_SQUARE_MAX_POSTS
        self.collected_posts = []

    async def scrape(self) -> list[dict]:
        self.collected_posts = []
        seen = set()

        for attempt in range(2):
            launch_args = [] if attempt == 0 else ["--no-proxy-server"]
            try:
                async with async_playwright() as p:
                    browser = await p.chromium.launch(
                        headless=True, args=launch_args or None
                    )
                    try:
                        context = await browser.new_context(
                            user_agent=(
                                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) "
                                "Chrome/120.0.0.0 Safari/537.36"
                            ),
                            viewport={"width": 1280, "height": 800},
                        )

                        for hashtag in BINANCE_SQUARE_HASHTAGS:
                            if len(self.collected_posts) >= self.max_posts:
                                break
                            await self._scrape_hashtag(context, hashtag, seen)

                    finally:
                        await browser.close()
                break  # success, no retry needed

            except ProxyBroken:
                if attempt == 0:
                    print("[BinanceSquare] Proxy down, retrying direct...")
                    self.collected_posts = []
                    seen.clear()
                    continue
            except Exception as e:
                print(f"[BinanceSquare] Browser error: {e}")
                break

        # Deduplicate
        final = []
        seen2 = set()
        for p in self.collected_posts:
            key = p["text"][:80]
            if key not in seen2:
                seen2.add(key)
                final.append(p)

        print(f"[BinanceSquare] Total unique posts: {len(final)}")
        return final[:self.max_posts]

    async def _scrape_hashtag(self, context, hashtag: str, seen: set):
        """Scrape a single hashtag with full error isolation."""
        page = None
        try:
            page = await context.new_page()
            page.on("response", self._on_response)

            url = f"https://www.binance.com/en/square/hashtag/{hashtag}"
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(5000)

            # Deep scroll with timeout guard
            for _ in range(20):
                if len(self.collected_posts) >= self.max_posts:
                    break
                try:
                    await page.evaluate("window.scrollBy(0, window.innerHeight * 2)")
                    await page.wait_for_timeout(1500)
                except Exception:
                    break

            # DOM fallback
            dom_posts = await self._scrape_from_dom(page)
            for post in dom_posts:
                key = post["text"][:80]
                if key not in seen:
                    seen.add(key)
                    self.collected_posts.append(post)

        except Exception as e:
            if is_proxy_error(e):
                raise ProxyBroken() from e
            if "Timeout" not in str(e):
                print(f"[BinanceSquare] #{hashtag} error: {e}")
        finally:
            if page:
                try:
                    await page.close()
                except Exception:
                    pass

    async def _on_response(self, response):
        if "/bapi/" not in response.url:
            return
        try:
            if response.status == 200 and "application/json" in (
                response.headers.get("content-type", "")
            ):
                body = await response.json()
                posts = self._extract_posts_from_api(body)
                self.collected_posts.extend(posts)
        except Exception:
            pass

    def _extract_posts_from_api(self, data: dict) -> list[dict]:
        posts = []

        def _search(obj, depth=0):
            if depth > 5:
                return
            if isinstance(obj, dict):
                if "content" in obj and isinstance(obj["content"], str):
                    text = obj["content"]
                    if len(text) > 10:
                        posts.append({
                            "source": "binance_square",
                            "text": text[:800],
                            "author": obj.get("nickname", obj.get("userName", "")),
                            "timestamp": obj.get("createTime", ""),
                            "likes": obj.get("likeCount", 0),
                        })
                for v in obj.values():
                    _search(v, depth + 1)
            elif isinstance(obj, list):
                for item in obj:
                    _search(item, depth + 1)

        _search(data)
        return posts

    async def _scrape_from_dom(self, page) -> list[dict]:
        posts = []
        try:
            all_text = await page.evaluate("""
                () => {
                    const texts = [];
                    const seen = new Set();
                    document.querySelectorAll('p, span, div, article').forEach(el => {
                        const t = el.innerText?.trim();
                        if (t && t.length > 30 && t.length < 2000 && !seen.has(t.substring(0, 80))) {
                            const lower = t.toLowerCase();
                            if (lower.includes('btc') || lower.includes('bitcoin')
                                || lower.includes('crypto') || lower.includes('市场')
                                || lower.includes('恐慌') || lower.includes('暴跌')
                                || lower.includes('bull') || lower.includes('bear')) {
                                seen.add(t.substring(0, 80));
                                texts.push(t.substring(0, 800));
                            }
                        }
                    });
                    return texts;
                }
            """)
            for text in all_text:
                posts.append({
                    "source": "binance_square",
                    "text": text,
                    "author": "",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "likes": 0,
                })
        except Exception:
            pass
        return posts


def scrape_binance_square() -> list[dict]:
    return asyncio.run(BinanceSquareScraper().scrape())
