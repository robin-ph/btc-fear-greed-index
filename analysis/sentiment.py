"""Stage 1: LLM sentiment analysis via OpenRouter API.

Mega-batch design: packs 800 posts per API call.
Uses free models via OpenRouter with automatic fallback.
"""

import json
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np

from llm_client import get_client

MEGA_BATCH_SIZE = 800
MAX_CONCURRENT = 5
MAX_TEXT_LEN = 200


@dataclass
class SentimentStats:
    """Statistical summary of sentiment analysis."""
    total_posts: int = 0
    analyzed_posts: int = 0

    mean_score: float = 50.0
    median_score: float = 50.0
    std_score: float = 0.0

    extreme_fear_ratio: float = 0.0
    fear_ratio: float = 0.0
    neutral_ratio: float = 0.0
    greed_ratio: float = 0.0
    extreme_greed_ratio: float = 0.0

    weighted_score: float = 50.0
    source_scores: dict = field(default_factory=dict)

    top_fear_posts: list = field(default_factory=list)
    top_greed_posts: list = field(default_factory=list)
    representative_posts: list = field(default_factory=list)

    def to_fear_score(self) -> float:
        """Convert to 0-100 fear score (invert: low sentiment = high fear)."""
        return round(100 - self.weighted_score, 2)


class SentimentAnalyzer:
    """Analyze sentiment using OpenRouter API with mega-batch prompts."""

    def __init__(self):
        self.llm = get_client()

    def analyze_all(self, posts: list[dict]) -> SentimentStats:
        if not posts:
            return SentimentStats()

        valid_posts = [p for p in posts if len(p.get("text", "")) > 15]

        n_batches = max(1, -(-len(valid_posts) // MEGA_BATCH_SIZE))
        print(f"[Sentiment] Scoring {len(valid_posts)} posts in {n_batches} mega-batch(es), "
              f"{MAX_CONCURRENT} concurrent, model={self.llm.current_model}")

        scored_posts = self._mega_batch_score(valid_posts)
        print(f"[Sentiment] Successfully scored {len(scored_posts)} posts")

        if not scored_posts:
            return SentimentStats()

        return self._compute_stats(scored_posts, len(posts))

    def _call_llm(self, prompt: str) -> str:
        return self.llm.call(prompt, temperature=0.1)

    # ── Mega-batch scoring ──

    def _mega_batch_score(self, posts: list[dict]) -> list[dict]:
        batches = []
        for i in range(0, len(posts), MEGA_BATCH_SIZE):
            batches.append(posts[i:i + MEGA_BATCH_SIZE])

        scored = []
        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT) as executor:
            futures = {
                executor.submit(self._score_one_batch, batch, idx): idx
                for idx, batch in enumerate(batches)
            }
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    batch_results = future.result()
                    scored.extend(batch_results)
                    print(f"[Sentiment] Batch {idx + 1}/{len(batches)} done "
                          f"({len(batch_results)} scored)")
                except Exception as e:
                    print(f"[Sentiment] Batch {idx + 1} failed: {e}")
                    scored.extend(self._fallback_score(batches[idx]))
                    print(f"[Sentiment] Batch {idx + 1} fell back to keyword scoring")

        return scored

    def _score_one_batch(self, batch: list[dict], batch_idx: int) -> list[dict]:
        post_lines = []
        for i, post in enumerate(batch):
            text = post.get("text", "")[:MAX_TEXT_LEN].replace("\n", " ").strip()
            post_lines.append(f"{i}|{text}")

        posts_block = "\n".join(post_lines)

        prompt = f"""Rate each post's BTC market sentiment. Scale: 0=extreme fear, 50=neutral, 100=extreme greed.

Rules:
- 0-20: panic selling, crash fear, liquidation despair
- 40-60: questions, news, DCA, wallet talk, discussion threads, neutral analysis
- 80-100: FOMO, mooning, ATH euphoria
- Sarcasm → rate the actual underlying sentiment
- Non-English → analyze content meaning

{len(batch)} posts (format: index|text):
{posts_block}

Reply with ONLY a JSON array of [index, score] pairs. No explanation.
Example: [[0,25],[1,72],[2,50]]"""

        text = self._call_llm(prompt)

        start = text.find("[")
        end = text.rfind("]") + 1
        if start < 0 or end <= start:
            raise ValueError(f"No JSON array in response (len={len(text)})")

        scores_array = json.loads(text[start:end])

        score_map = {}
        for item in scores_array:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                try:
                    score_map[int(item[0])] = max(0, min(100, float(item[1])))
                except (ValueError, TypeError):
                    continue

        scored = []
        for i, post in enumerate(batch):
            score = score_map.get(i, 50)
            weight = self._compute_weight(post)
            scored.append({**post, "_score": score, "_weight": weight})

        return scored

    # ── Fallback ──

    def _fallback_score(self, batch: list[dict]) -> list[dict]:
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

    # ── Statistics ──

    def _compute_weight(self, post: dict) -> float:
        w = 1.0
        for key in ["score", "num_comments", "likes", "retweets"]:
            val = abs(post.get(key, 0))
            if val > 0:
                w += min(np.log1p(val), 5)
        return w

    def _compute_stats(self, scored_posts: list[dict], total_raw: int) -> SentimentStats:
        scores = np.array([p["_score"] for p in scored_posts])
        weights = np.array([p["_weight"] for p in scored_posts])

        weighted_avg = float(np.average(scores, weights=weights))

        n = len(scores)
        extreme_fear = float(np.sum(scores < 20) / n)
        fear = float(np.sum((scores >= 20) & (scores < 40)) / n)
        neutral = float(np.sum((scores >= 40) & (scores < 60)) / n)
        greed = float(np.sum((scores >= 60) & (scores < 80)) / n)
        extreme_greed = float(np.sum(scores >= 80) / n)

        source_scores = {}
        for p in scored_posts:
            src = p.get("source", "unknown")
            if src not in source_scores:
                source_scores[src] = []
            source_scores[src].append(p["_score"])
        source_avgs = {s: round(float(np.mean(v)), 1) for s, v in source_scores.items()}

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
    lines = [
        "",
        "┌─────────────────────────────────────────────────┐",
        "│    Stage 1: LLM Sentiment Analysis (Nemotron)    │",
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
