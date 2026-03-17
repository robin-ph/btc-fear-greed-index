"""Stage 1: LLM-powered sentiment analysis of ALL scraped social data.

Uses DeepSeek API to batch-analyze all posts with proper crypto context
understanding. VADER fails on crypto content (sarcasm, slang, neutral
discussion posts scored as extreme greed).

DeepSeek-chat is extremely cheap (~$0.001 per 1000 tokens) so analyzing
3000 posts costs essentially nothing.
"""

import json
import re
import time
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
from openai import OpenAI


import os
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
BATCH_SIZE = 40  # Posts per batch


@dataclass
class SentimentStats:
    """Statistical summary of sentiment analysis."""
    total_posts: int = 0
    analyzed_posts: int = 0

    # Sentiment distribution (0-100, 0=extreme fear, 100=extreme greed)
    mean_score: float = 50.0
    median_score: float = 50.0
    std_score: float = 0.0

    # Extreme ratios
    extreme_fear_ratio: float = 0.0
    fear_ratio: float = 0.0
    neutral_ratio: float = 0.0
    greed_ratio: float = 0.0
    extreme_greed_ratio: float = 0.0

    # Weighted score (by engagement)
    weighted_score: float = 50.0

    # Per-source breakdown
    source_scores: dict = field(default_factory=dict)

    # Representative posts for OASIS
    top_fear_posts: list = field(default_factory=list)
    top_greed_posts: list = field(default_factory=list)
    representative_posts: list = field(default_factory=list)

    def to_fear_score(self) -> float:
        """Convert to 0-100 fear score (invert: low sentiment = high fear)."""
        return round(100 - self.weighted_score, 2)


class SentimentAnalyzer:
    """Analyze sentiment using DeepSeek LLM for crypto-aware scoring."""

    def __init__(self):
        self.client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
        )

    def analyze_all(self, posts: list[dict], hours_filter: int = 24) -> SentimentStats:
        """Batch-analyze all posts with DeepSeek."""
        if not posts:
            return SentimentStats()

        # Filter out very short / empty posts
        valid_posts = [p for p in posts if len(p.get("text", "")) > 15]

        # Batch score with DeepSeek
        print(f"[Sentiment] Scoring {len(valid_posts)} posts in batches of {BATCH_SIZE}...")
        scored_posts = self._batch_score(valid_posts)
        print(f"[Sentiment] Successfully scored {len(scored_posts)} posts")

        if not scored_posts:
            return SentimentStats()

        # Compute statistics
        return self._compute_stats(scored_posts, len(posts))

    def _batch_score(self, posts: list[dict]) -> list[dict]:
        """Score all posts in parallel batches using DeepSeek."""
        batches = []
        for i in range(0, len(posts), BATCH_SIZE):
            batches.append(posts[i:i + BATCH_SIZE])

        scored = []
        # Process batches with thread pool (4 concurrent API calls)
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(self._score_batch, batch, idx): idx
                for idx, batch in enumerate(batches)
            }
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    batch_results = future.result()
                    scored.extend(batch_results)
                    if (idx + 1) % 10 == 0:
                        print(f"[Sentiment] Completed {idx + 1}/{len(batches)} batches...")
                except Exception as e:
                    print(f"[Sentiment] Batch {idx} failed: {e}")

        return scored

    def _score_batch(self, batch: list[dict], batch_idx: int) -> list[dict]:
        """Score a single batch of posts with DeepSeek."""
        # Build the prompt with numbered posts
        post_lines = []
        for i, post in enumerate(batch):
            text = post.get("text", "")[:300].replace("\n", " ")
            source = post.get("source", "?")
            post_lines.append(f"{i}|{source}|{text}")

        posts_block = "\n".join(post_lines)

        prompt = f"""Score each crypto social media post's MARKET SENTIMENT on a 0-100 scale.

IMPORTANT RULES:
- 0 = extreme fear/panic about BTC price (selling, crashing, liquidation, despair)
- 50 = neutral (questions, news, discussion not expressing fear or greed)
- 100 = extreme greed/euphoria about BTC price (mooning, ATH, FOMO buying)
- Posts about personal purchases, DCA, wallets, mining hardware = 50 (neutral, NOT greed)
- "Daily Discussion" threads, FAQ posts, mod posts = 50 (neutral)
- Sarcasm/irony: score based on the ACTUAL sentiment being expressed
- News/analysis without clear sentiment = 50
- Non-English posts: analyze based on content

Posts (format: index|source|text):
{posts_block}

Output ONLY a JSON array of [index, score] pairs. Example: [[0,25],[1,72],[2,50]]
No explanation, just the JSON array."""

        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000,
                temperature=0.1,
            )

            result_text = response.choices[0].message.content.strip()

            # Parse JSON array
            # Find the array in the response
            start = result_text.find("[")
            end = result_text.rfind("]") + 1
            if start >= 0 and end > start:
                scores_array = json.loads(result_text[start:end])
            else:
                return self._fallback_score(batch)

            # Map scores back to posts
            score_map = {}
            for item in scores_array:
                if isinstance(item, list) and len(item) == 2:
                    score_map[int(item[0])] = max(0, min(100, float(item[1])))

            scored = []
            for i, post in enumerate(batch):
                score = score_map.get(i, 50)
                weight = self._compute_weight(post)
                scored.append({
                    **post,
                    "_score": score,
                    "_weight": weight,
                })

            return scored

        except Exception as e:
            # Fallback to simple keyword scoring
            return self._fallback_score(batch)

    def _fallback_score(self, batch: list[dict]) -> list[dict]:
        """Simple keyword-based fallback if API fails."""
        fear_words = {"crash", "dump", "liquidat", "rekt", "panic", "sell", "bear",
                      "plunge", "collapse", "blood", "fear", "暴跌", "崩盘", "爆仓", "恐慌"}
        greed_words = {"moon", "pump", "bull", "rally", "ath", "buy", "hodl",
                       "diamond", "rocket", "暴涨", "牛市", "起飞", "梭哈"}

        scored = []
        for post in batch:
            text = post.get("text", "").lower()
            fear_count = sum(1 for w in fear_words if w in text)
            greed_count = sum(1 for w in greed_words if w in text)

            if fear_count > greed_count:
                score = max(10, 50 - fear_count * 12)
            elif greed_count > fear_count:
                score = min(90, 50 + greed_count * 12)
            else:
                score = 50

            scored.append({**post, "_score": score, "_weight": self._compute_weight(post)})
        return scored

    def _compute_weight(self, post: dict) -> float:
        """Engagement-based weight."""
        w = 1.0
        for key in ["score", "num_comments", "likes", "retweets"]:
            val = abs(post.get(key, 0))
            if val > 0:
                w += min(np.log1p(val), 5)
        return w

    def _compute_stats(self, scored_posts: list[dict], total_raw: int) -> SentimentStats:
        """Compute statistics from scored posts."""
        scores = np.array([p["_score"] for p in scored_posts])
        weights = np.array([p["_weight"] for p in scored_posts])

        # Weighted average
        weighted_avg = float(np.average(scores, weights=weights))

        # Distribution
        n = len(scores)
        extreme_fear = float(np.sum(scores < 20) / n)
        fear = float(np.sum((scores >= 20) & (scores < 40)) / n)
        neutral = float(np.sum((scores >= 40) & (scores < 60)) / n)
        greed = float(np.sum((scores >= 60) & (scores < 80)) / n)
        extreme_greed = float(np.sum(scores >= 80) / n)

        # Per-source
        source_scores = {}
        for p in scored_posts:
            src = p.get("source", "unknown")
            if src not in source_scores:
                source_scores[src] = []
            source_scores[src].append(p["_score"])
        source_avgs = {s: round(float(np.mean(v)), 1) for s, v in source_scores.items()}

        # Select posts for OASIS
        sorted_by_score = sorted(scored_posts, key=lambda p: p["_score"])
        top_fear = sorted_by_score[:30]
        top_greed = sorted_by_score[-30:]
        representative = self._stratified_sample(scored_posts, n=50)

        return SentimentStats(
            total_posts=total_raw,
            analyzed_posts=len(scored_posts),
            mean_score=round(float(np.mean(scores)), 2),
            median_score=round(float(np.median(scores)), 2),
            std_score=round(float(np.std(scores)), 2),
            extreme_fear_ratio=round(extreme_fear, 4),
            fear_ratio=round(fear, 4),
            neutral_ratio=round(neutral, 4),
            greed_ratio=round(greed, 4),
            extreme_greed_ratio=round(extreme_greed, 4),
            weighted_score=round(weighted_avg, 2),
            source_scores=source_avgs,
            top_fear_posts=[self._clean(p) for p in top_fear],
            top_greed_posts=[self._clean(p) for p in top_greed],
            representative_posts=[self._clean(p) for p in representative],
        )

    def _stratified_sample(self, posts: list[dict], n: int = 50) -> list[dict]:
        """Select stratified sample across sentiment buckets."""
        buckets = {"ef": [], "f": [], "n": [], "g": [], "eg": []}
        for p in posts:
            s = p["_score"]
            if s < 20: buckets["ef"].append(p)
            elif s < 40: buckets["f"].append(p)
            elif s < 60: buckets["n"].append(p)
            elif s < 80: buckets["g"].append(p)
            else: buckets["eg"].append(p)

        sample = []
        total = sum(len(v) for v in buckets.values())
        if total == 0:
            return []

        for bucket_posts in buckets.values():
            if not bucket_posts:
                continue
            count = max(1, round(len(bucket_posts) / total * n))
            bucket_posts.sort(key=lambda p: p["_weight"], reverse=True)
            sample.extend(bucket_posts[:count])

        return sample[:n]

    def _clean(self, post: dict) -> dict:
        return {k: v for k, v in post.items() if not k.startswith("_")}


def format_sentiment_report(stats: SentimentStats) -> str:
    """Format sentiment analysis report."""
    lines = [
        "",
        "┌─────────────────────────────────────────────────┐",
        "│    Stage 1: LLM Sentiment Analysis (DeepSeek)   │",
        "├─────────────────────────────────────────────────┤",
        f"│  Posts analyzed: {stats.analyzed_posts:>6,d} / {stats.total_posts:>6,d}          │",
        f"│  Mean sentiment:  {stats.mean_score:>5.1f} / 100                 │",
        f"│  Weighted score:  {stats.weighted_score:>5.1f} / 100                 │",
        f"│  Std deviation:   {stats.std_score:>5.1f}                        │",
        "├─────────────────────────────────────────────────┤",
        "│  Distribution:                                   │",
    ]

    bar_width = 30
    for label, ratio in [
        ("Extreme Fear", stats.extreme_fear_ratio),
        ("Fear        ", stats.fear_ratio),
        ("Neutral     ", stats.neutral_ratio),
        ("Greed       ", stats.greed_ratio),
        ("Extreme Grd ", stats.extreme_greed_ratio),
    ]:
        filled = int(ratio * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)
        pct = ratio * 100
        lines.append(f"│  {label} [{bar}] {pct:>5.1f}% │")

    lines.append("├─────────────────────────────────────────────────┤")
    lines.append("│  Per-source sentiment (0=fear, 100=greed):      │")
    for src, score in sorted(stats.source_scores.items()):
        lines.append(f"│    {src:<20s} {score:>5.1f}                  │")

    lines.append(f"├─────────────────────────────────────────────────┤")
    lines.append(f"│  → Fear Score: {stats.to_fear_score():>5.1f} / 100                    │")
    lines.append("└─────────────────────────────────────────────────┘")

    return "\n".join(lines)
