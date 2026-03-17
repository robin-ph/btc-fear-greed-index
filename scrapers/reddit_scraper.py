"""Reddit mass scraper - RSS feeds across many subreddits and sort types."""

import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import requests

from config.settings import REDDIT_MAX_POSTS, REDDIT_SUBREDDITS


class RedditScraper:
    def __init__(self):
        self.max_posts = REDDIT_MAX_POSTS
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
            ),
        })

    def scrape(self) -> list[dict]:
        """Scrape Reddit via RSS feeds across all subreddits and sort types."""
        posts = []
        seen_titles = set()
        sorts = ["hot", "new", "rising", "top"]

        for sub_name in REDDIT_SUBREDDITS:
            if len(posts) >= self.max_posts:
                break
            for sort in sorts:
                if len(posts) >= self.max_posts:
                    break
                rss_posts = self._fetch_rss(sub_name, sort)
                for p in rss_posts:
                    # Deduplicate
                    key = p["text"][:80]
                    if key not in seen_titles:
                        seen_titles.add(key)
                        posts.append(p)
                # Rate limit: 1 req/sec to avoid 429
                time.sleep(1)

        # Also search for BTC-specific posts across Reddit
        search_terms = [
            "BTC crash", "Bitcoin fear", "crypto panic",
            "Bitcoin sell", "BTC liquidation", "crypto bear market",
            "Bitcoin bottom", "BTC dump", "crypto recession",
        ]
        for term in search_terms:
            if len(posts) >= self.max_posts:
                break
            search_posts = self._fetch_search_rss(term)
            for p in search_posts:
                key = p["text"][:80]
                if key not in seen_titles:
                    seen_titles.add(key)
                    posts.append(p)
            time.sleep(1)

        print(f"[Reddit] Collected {len(posts)} unique posts from {len(REDDIT_SUBREDDITS)} subreddits")
        return posts[:self.max_posts]

    def _fetch_rss(self, subreddit: str, sort: str) -> list[dict]:
        """Fetch posts via Reddit RSS feed."""
        posts = []
        try:
            url = f"https://www.reddit.com/r/{subreddit}/{sort}/.rss?limit=100"
            resp = self.session.get(url, timeout=15)
            if resp.status_code != 200:
                return []
            posts = self._parse_atom(resp.text, subreddit)
        except Exception as e:
            if "429" not in str(e):
                print(f"[Reddit] RSS error r/{subreddit}/{sort}: {e}")
        return posts

    def _fetch_search_rss(self, query: str) -> list[dict]:
        """Search Reddit via RSS."""
        posts = []
        try:
            url = f"https://www.reddit.com/search/.rss?q={query}&sort=new&limit=100"
            resp = self.session.get(url, timeout=15)
            if resp.status_code != 200:
                return []
            posts = self._parse_atom(resp.text, f"search:{query}")
        except Exception:
            pass
        return posts

    def _parse_atom(self, xml_text: str, subreddit: str) -> list[dict]:
        """Parse Atom XML feed."""
        posts = []
        try:
            root = ET.fromstring(xml_text)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            for entry in root.findall("atom:entry", ns):
                title_el = entry.find("atom:title", ns)
                content_el = entry.find("atom:content", ns)
                author_el = entry.find("atom:author/atom:name", ns)
                updated_el = entry.find("atom:updated", ns)

                title = title_el.text if title_el is not None else ""
                author = author_el.text if author_el is not None else ""
                timestamp = updated_el.text if updated_el is not None else ""

                body = ""
                if content_el is not None and content_el.text:
                    body = re.sub(r"<[^>]+>", " ", content_el.text)
                    body = re.sub(r"\s+", " ", body).strip()[:500]

                text = title
                if body:
                    text += " " + body

                if text and len(text) > 10:
                    posts.append({
                        "source": "reddit",
                        "subreddit": subreddit,
                        "text": text[:800],
                        "author": author.replace("/u/", ""),
                        "timestamp": timestamp,
                        "score": 0,
                        "num_comments": 0,
                    })
        except ET.ParseError:
            pass
        return posts


def scrape_reddit() -> list[dict]:
    return RedditScraper().scrape()
