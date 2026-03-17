"""Twitter/X mass scraper via Nitter instances."""

import asyncio
from datetime import datetime, timezone
from playwright.async_api import async_playwright

from config.settings import TWITTER_MAX_TWEETS, TWITTER_KEYWORDS


NITTER_INSTANCES = [
    "https://nitter.poast.org",
    "https://nitter.privacydev.net",
    "https://nitter.net",
    "https://nitter.1d4.us",
    "https://nitter.kavin.rocks",
]


class TwitterScraper:
    def __init__(self):
        self.max_tweets = TWITTER_MAX_TWEETS

    async def scrape(self) -> list[dict]:
        """Scrape BTC tweets from multiple Nitter instances and keywords."""
        all_tweets = []
        seen = set()

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
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

                working = False
                for keyword in TWITTER_KEYWORDS:
                    if len(all_tweets) >= self.max_tweets:
                        break
                    try:
                        page = await context.new_page()
                        tweets = await self._scrape_search(page, nitter_url, keyword)
                        for t in tweets:
                            key = t["text"][:80]
                            if key not in seen:
                                seen.add(key)
                                all_tweets.append(t)
                                working = True
                        await page.close()
                    except Exception:
                        await page.close()
                        continue

                if working:
                    print(f"[Twitter] {nitter_url}: collected {len(all_tweets)} tweets so far")
                    # Try pagination on this working instance
                    for keyword in TWITTER_KEYWORDS[:5]:
                        if len(all_tweets) >= self.max_tweets:
                            break
                        for page_num in range(2, 6):  # Pages 2-5
                            try:
                                page = await context.new_page()
                                tweets = await self._scrape_search_page(
                                    page, nitter_url, keyword, page_num
                                )
                                for t in tweets:
                                    key = t["text"][:80]
                                    if key not in seen:
                                        seen.add(key)
                                        all_tweets.append(t)
                                await page.close()
                            except Exception:
                                await page.close()
                                break
                    break  # Found a working instance, don't try others

            await browser.close()

        print(f"[Twitter] Total unique tweets: {len(all_tweets)}")
        return all_tweets[:self.max_tweets]

    async def _scrape_search(self, page, base_url: str, term: str) -> list[dict]:
        """Scrape tweets from a Nitter search page."""
        url = f"{base_url}/search?f=tweets&q={term}"
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        await page.wait_for_timeout(2000)
        return await self._extract_tweets(page)

    async def _scrape_search_page(self, page, base_url: str, term: str, page_num: int) -> list[dict]:
        """Scrape a specific page of Nitter search results."""
        # Nitter pagination uses cursor parameter
        url = f"{base_url}/search?f=tweets&q={term}&cursor={page_num}"
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        await page.wait_for_timeout(2000)
        return await self._extract_tweets(page)

    async def _extract_tweets(self, page) -> list[dict]:
        """Extract tweet data from a Nitter page."""
        tweets = []
        # Nitter tweet selectors
        items = await page.query_selector_all(".timeline-item")
        if not items:
            items = await page.query_selector_all(".tweet-body")
        if not items:
            items = await page.query_selector_all("[class*='tweet']")

        for item in items:
            try:
                # Get tweet content
                content_el = await item.query_selector(".tweet-content, .media-body")
                if content_el:
                    text = await content_el.inner_text()
                else:
                    text = await item.inner_text()

                text = text.strip()
                if len(text) > 15:
                    # Try to get stats
                    stats = {}
                    for stat_name in ["replies", "retweets", "quotes", "hearts"]:
                        stat_el = await item.query_selector(f".icon-{stat_name} + span, .tweet-stat .{stat_name}")
                        if stat_el:
                            try:
                                stats[stat_name] = int((await stat_el.inner_text()).replace(",", ""))
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
