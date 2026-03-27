"""Twitter/X scraper via Nitter — hardened for daily cron runs.

Nitter instances are unreliable. This scraper tries multiple instances
and gracefully returns empty if all are down.
"""

import asyncio
from datetime import datetime, timezone
from playwright.async_api import async_playwright

from config.settings import TWITTER_MAX_TWEETS, TWITTER_KEYWORDS
from scrapers import ProxyBroken, is_proxy_error


# Expanded instance list for better availability
NITTER_INSTANCES = [
    "https://nitter.poast.org",
    "https://nitter.privacydev.net",
    "https://nitter.net",
    "https://nitter.1d4.us",
    "https://nitter.kavin.rocks",
    "https://nitter.cz",
    "https://nitter.esmailelbob.xyz",
    "https://nitter.tiekoetter.com",
]


class TwitterScraper:
    def __init__(self):
        self.max_tweets = TWITTER_MAX_TWEETS

    async def scrape(self) -> list[dict]:
        all_tweets = []
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
                                "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
                            ),
                            viewport={"width": 1280, "height": 900},
                        )

                        for nitter_url in NITTER_INSTANCES:
                            if len(all_tweets) >= self.max_tweets:
                                break

                            working = await self._try_instance(
                                context, nitter_url, seen, all_tweets
                            )

                            if working:
                                print(f"[Twitter] {nitter_url}: {len(all_tweets)} tweets")
                                await self._paginate_instance(
                                    context, nitter_url, seen, all_tweets
                                )
                                break

                    finally:
                        await browser.close()
                break  # success

            except ProxyBroken:
                if attempt == 0:
                    print("[Twitter] Proxy down, retrying direct...")
                    all_tweets.clear()
                    seen.clear()
                    continue
            except Exception as e:
                print(f"[Twitter] Browser error: {e}")
                break

        if not all_tweets:
            print("[Twitter] All Nitter instances down — 0 tweets collected")
        else:
            print(f"[Twitter] Total unique tweets: {len(all_tweets)}")

        return all_tweets[:self.max_tweets]

    async def _try_instance(
        self, context, nitter_url: str, seen: set, all_tweets: list
    ) -> bool:
        """Try scraping keywords from one Nitter instance. Returns True if it works."""
        working = False
        for keyword in TWITTER_KEYWORDS[:5]:  # Quick probe with 5 keywords
            if len(all_tweets) >= self.max_tweets:
                break
            page = None
            try:
                page = await context.new_page()
                tweets = await self._scrape_search(page, nitter_url, keyword)
                for t in tweets:
                    key = t["text"][:80]
                    if key not in seen:
                        seen.add(key)
                        all_tweets.append(t)
                        working = True
            except Exception:
                pass
            finally:
                if page:
                    try:
                        await page.close()
                    except Exception:
                        pass
        return working

    async def _paginate_instance(
        self, context, nitter_url: str, seen: set, all_tweets: list
    ):
        """Paginate remaining keywords on a working instance."""
        for keyword in TWITTER_KEYWORDS[5:]:
            if len(all_tweets) >= self.max_tweets:
                break
            page = None
            try:
                page = await context.new_page()
                tweets = await self._scrape_search(page, nitter_url, keyword)
                for t in tweets:
                    key = t["text"][:80]
                    if key not in seen:
                        seen.add(key)
                        all_tweets.append(t)
            except Exception:
                pass
            finally:
                if page:
                    try:
                        await page.close()
                    except Exception:
                        pass

    async def _scrape_search(self, page, base_url: str, term: str) -> list[dict]:
        url = f"{base_url}/search?f=tweets&q={term}"
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        except Exception as e:
            if is_proxy_error(e):
                raise ProxyBroken() from e
            raise
        await page.wait_for_timeout(2000)
        return await self._extract_tweets(page)

    async def _extract_tweets(self, page) -> list[dict]:
        tweets = []
        items = await page.query_selector_all(".timeline-item")
        if not items:
            items = await page.query_selector_all(".tweet-body")
        if not items:
            items = await page.query_selector_all("[class*='tweet']")

        for item in items:
            try:
                content_el = await item.query_selector(".tweet-content, .media-body")
                if content_el:
                    text = await content_el.inner_text()
                else:
                    text = await item.inner_text()

                text = text.strip()
                if len(text) > 15:
                    stats = {}
                    for stat_name in ["replies", "retweets", "quotes", "hearts"]:
                        stat_el = await item.query_selector(
                            f".icon-{stat_name} + span, .tweet-stat .{stat_name}"
                        )
                        if stat_el:
                            try:
                                stats[stat_name] = int(
                                    (await stat_el.inner_text()).replace(",", "")
                                )
                            except ValueError:
                                pass

                    tweets.append({
                        "source": "twitter",
                        "text": text[:800],
                        "author": "",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "likes": stats.get("hearts", 0),
                        "retweets": stats.get("retweets", 0),
                    })
            except Exception:
                continue

        return tweets


def scrape_twitter() -> list[dict]:
    return asyncio.run(TwitterScraper().scrape())
