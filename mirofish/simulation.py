"""Two-stage MiroFish sentiment pipeline (OpenRouter API).

Stage 1: Mega-batch sentiment scoring via Nemotron
Stage 2: 500-agent multi-round conversation simulation
         10 agent types × 3 rounds, batched by type (30 API calls total)
         Each type generates posts for ALL agents of that type per round
"""

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from analysis.sentiment import SentimentAnalyzer, SentimentStats, format_sentiment_report
from llm_client import get_client

NUM_ROUNDS = 3
TYPE_CONCURRENCY = 3  # Concurrent API calls per round (conservative for free model)

# ── 500 agents: 10 types with realistic distribution ──
AGENT_TYPES = [
    {
        "name": "Retail High Fear",
        "count": 120,
        "system": (
            "You represent 120 retail crypto investors who bought BTC between $60K-$73K. "
            "They're underwater, panic-prone, check prices every 5 minutes, and heavily "
            "influenced by fear on social media. Generate {n_posts} SHORT diverse posts "
            "(1-2 sentences each) from different individuals in this group. "
            "Vary their intensity: some are about to sell, some are holding but terrified, "
            "some are asking for reassurance. Number each post."
        ),
        "posts_per_round": 8,
    },
    {
        "name": "Moderate Retail",
        "count": 80,
        "system": (
            "You represent 80 retail investors with some crypto experience. "
            "They bought BTC between $30K-$55K, in profit but worried about giving back gains. "
            "They try to be rational but get swayed by crowd sentiment. "
            "Generate {n_posts} SHORT diverse posts (1-2 sentences each). "
            "Vary: some cautious optimists, some starting to worry, some DCA believers. Number each."
        ),
        "posts_per_round": 5,
    },
    {
        "name": "Active Trader",
        "count": 60,
        "system": (
            "You represent 60 active crypto traders focused on technical analysis. "
            "They trade daily/weekly using chart patterns, support/resistance levels, momentum. "
            "Generate {n_posts} SHORT diverse posts (1-2 sentences each). "
            "Reference specific price levels, patterns, indicators. Vary between bullish and bearish reads. Number each."
        ),
        "posts_per_round": 4,
    },
    {
        "name": "Leveraged Trader",
        "count": 40,
        "system": (
            "You represent 40 leveraged crypto traders running 5-50x on BTC futures. "
            "They're extremely sensitive to price swings — a few percent move means liquidation. "
            "Generate {n_posts} SHORT intense posts (1-2 sentences each). "
            "Talk about leverage, liquidation levels, funding rates, rekt. Vary leverage levels. Number each."
        ),
        "posts_per_round": 3,
    },
    {
        "name": "Pure Newbie",
        "count": 45,
        "system": (
            "You represent 45 complete crypto newbies who bought BTC last month. "
            "No understanding of market cycles, TA, or fundamentals. Heard about BTC from TikTok/friends. "
            "Generate {n_posts} SHORT diverse posts (1-2 sentences each). "
            "Ask naive questions, express confusion, panic at any red day. Number each."
        ),
        "posts_per_round": 3,
    },
    {
        "name": "DeFi User",
        "count": 35,
        "system": (
            "You represent 35 DeFi users with BTC as collateral in lending protocols. "
            "They monitor health factors and liquidation thresholds obsessively. "
            "Generate {n_posts} SHORT posts (1-2 sentences each). "
            "Talk about collateral ratios, liquidation prices, depegs, protocol risk. Number each."
        ),
        "posts_per_round": 2,
    },
    {
        "name": "KOL Influencer",
        "count": 25,
        "system": (
            "You represent 25 crypto influencers with large followings. "
            "They amplify whatever narrative gets engagement — bearish during dumps, bullish during pumps. "
            "They use dramatic, sensational language. "
            "Generate {n_posts} SHORT viral-style posts (1-2 sentences each). "
            "Some bearish doom, some contrarian bullish calls. Use crypto slang. Number each."
        ),
        "posts_per_round": 3,
    },
    {
        "name": "Miner",
        "count": 20,
        "system": (
            "You represent 20 BTC miners with break-even costs $35K-$50K. "
            "They care about hashrate, difficulty, energy costs, mining profitability. "
            "Generate {n_posts} SHORT posts (1-2 sentences each). "
            "Provide mining perspective on price moves. Number each."
        ),
        "posts_per_round": 2,
    },
    {
        "name": "Institutional",
        "count": 25,
        "system": (
            "You represent 25 institutional investors (hedge funds, family offices). "
            "Data-driven, contrarian — they buy when retail panics. "
            "They look at on-chain data, macro indicators, risk metrics. "
            "Generate {n_posts} SHORT analytical posts (1-2 sentences each). "
            "Calm, measured, contrarian. Number each."
        ),
        "posts_per_round": 2,
    },
    {
        "name": "Diamond Hands OG",
        "count": 50,
        "system": (
            "You represent 50 long-term BTC holders since 2017. "
            "They've survived 3+ crashes of -80%. Nothing phases them. "
            "They believe in BTC fundamentals and see crashes as buying opportunities. "
            "Generate {n_posts} SHORT dismissive/calm posts (1-2 sentences each). "
            "Some zen, some mocking panic sellers, some quietly accumulating. Number each."
        ),
        "posts_per_round": 3,
    },
]


class MiroFishSimulator:
    def __init__(self):
        self.analyzer = SentimentAnalyzer()
        self.llm = get_client()

    def run_simulation(
        self, social_posts: list[dict], market_data: dict
    ) -> dict:
        """Two-stage pipeline: mega-batch analysis → 500-agent conversation."""

        # === Stage 1: Analyze ALL posts ===
        print(f"\n[Stage 1] Analyzing {len(social_posts)} posts via OpenRouter...")
        stats = self.analyzer.analyze_all(social_posts)
        print(format_sentiment_report(stats))

        stage1_score = stats.to_fear_score()
        print(f"[Stage 1] Base fear score: {stage1_score:.1f}/100")

        # === Stage 2: 500-agent conversation ===
        stage2_result = self._run_500_agent_conversation(stats, market_data)

        if stage2_result:
            stage2_score = stage2_result.get("sentiment_score", stage1_score)
            final_score = stage1_score * 0.4 + stage2_score * 0.6

            total_agents = sum(t["count"] for t in AGENT_TYPES)
            return {
                "sentiment_score": round(final_score, 2),
                "stage1_score": stage1_score,
                "stage2_score": stage2_score,
                "agent_responses": stage2_result.get("agent_responses", []),
                "method": "500_agent_conversation",
                "num_posts_analyzed": stats.analyzed_posts,
                "num_agents": total_agents,
                "num_rounds": NUM_ROUNDS,
                "sentiment_stats": {
                    "mean": stats.mean_score,
                    "median": stats.median_score,
                    "std": stats.std_score,
                    "extreme_fear_pct": round(stats.extreme_fear_ratio * 100, 1),
                    "fear_pct": round(stats.fear_ratio * 100, 1),
                    "neutral_pct": round(stats.neutral_ratio * 100, 1),
                    "greed_pct": round(stats.greed_ratio * 100, 1),
                    "extreme_greed_pct": round(stats.extreme_greed_ratio * 100, 1),
                    "source_scores": stats.source_scores,
                },
            }

        # Fallback
        print("[Stage 2] 500-agent simulation failed, using Stage 1 only")
        return {
            "sentiment_score": stage1_score,
            "stage1_score": stage1_score,
            "stage2_score": None,
            "agent_responses": [],
            "method": "statistical_only",
            "num_posts_analyzed": stats.analyzed_posts,
            "sentiment_stats": {
                "mean": stats.mean_score,
                "median": stats.median_score,
                "std": stats.std_score,
                "source_scores": stats.source_scores,
            },
        }

    def _call_llm(self, system: str, user: str, max_tokens: int = 800) -> str:
        """Call LLM with automatic model fallback."""
        return self.llm.call(user, system=system, temperature=0.85, max_tokens=max_tokens)

    def _run_500_agent_conversation(self, stats: SentimentStats, market_data: dict) -> dict:
        """Run 500 agents (batched by type) × 3 rounds of conversation.

        Each round: 10 API calls (one per agent type), each generating
        multiple posts from all agents of that type. ~30 API calls total.
        """
        raw = market_data.get("raw", {})

        fear_samples = "\n".join(
            f"  - {p.get('text', '')[:120]}"
            for p in stats.top_fear_posts[:5]
        )
        greed_samples = "\n".join(
            f"  - {p.get('text', '')[:120]}"
            for p in stats.top_greed_posts[:5]
        )

        market_context = (
            f"BTC: ${raw.get('price_usd', 0):,.0f} | 24h: {raw.get('change_24h_pct', 0):.2f}% "
            f"| Dominance: {raw.get('btc_dominance', 0):.1f}%\n"
            f"Sentiment from {stats.analyzed_posts:,d} real posts: "
            f"Fear {(stats.extreme_fear_ratio + stats.fear_ratio) * 100:.0f}% / "
            f"Neutral {stats.neutral_ratio * 100:.0f}% / "
            f"Greed {(stats.greed_ratio + stats.extreme_greed_ratio) * 100:.0f}%\n\n"
            f"Top fear posts:\n{fear_samples}\n\nTop greed posts:\n{greed_samples}"
        )

        all_posts = []
        total_agents = sum(t["count"] for t in AGENT_TYPES)

        try:
            for round_num in range(1, NUM_ROUNDS + 1):
                if round_num > 1:
                    time.sleep(12)  # Rate limit buffer

                print(f"[Stage 2] Round {round_num}/{NUM_ROUNDS} "
                      f"({total_agents} agents across {len(AGENT_TYPES)} types)...")

                if round_num == 1:
                    forum_context = (
                        f"Today's market:\n{market_context}\n\n"
                        f"React to this data on a crypto Reddit forum."
                    )
                else:
                    # Show recent posts from ALL types
                    recent = all_posts[-(total_agents // 3 * 2):]  # Last ~2 rounds worth
                    recent_text = "\n".join(
                        f"[{p['type']}] {p['text']}"
                        for p in recent[-40:]  # Cap at 40 to fit context
                    )
                    forum_context = (
                        f"Market:\n{market_context}\n\n"
                        f"Recent forum posts:\n{recent_text}\n\n"
                        f"Respond to the discussion. React to what others are saying."
                    )

                round_posts = self._run_round(forum_context, round_num)
                all_posts.extend(round_posts)

                # Print summary
                type_counts = {}
                for p in round_posts:
                    type_counts[p["type"]] = type_counts.get(p["type"], 0) + 1
                total_round = sum(type_counts.values())
                print(f"    Generated {total_round} posts from {len(type_counts)} types")

            # === Score the full conversation ===
            print(f"[Stage 2] Scoring {len(all_posts)} posts from {total_agents} agents...")
            result = self._score_conversation(all_posts, market_context)
            return result

        except Exception as e:
            print(f"[Stage 2] Error: {e}")
            return None

    def _run_round(self, forum_context: str, round_num: int) -> list[dict]:
        """Run all agent types for one round, with controlled concurrency."""
        all_posts = []

        with ThreadPoolExecutor(max_workers=TYPE_CONCURRENCY) as executor:
            futures = {
                executor.submit(
                    self._generate_type_posts, agent_type, forum_context, round_num
                ): agent_type
                for agent_type in AGENT_TYPES
            }
            for future in as_completed(futures):
                agent_type = futures[future]
                try:
                    posts = future.result()
                    all_posts.extend(posts)
                except Exception as e:
                    print(f"    {agent_type['name']} failed: {e}")

        return all_posts

    def _generate_type_posts(
        self, agent_type: dict, forum_context: str, round_num: int
    ) -> list[dict]:
        """Generate posts for ALL agents of one type in a single API call."""
        n_posts = agent_type["posts_per_round"]
        system = agent_type["system"].format(n_posts=n_posts)

        text = self._call_llm(system, forum_context, max_tokens=600)

        if text == "(no response)":
            return []

        # Parse numbered posts from response
        posts = []
        for line in text.split("\n"):
            line = line.strip()
            if not line or len(line) < 10:
                continue
            # Strip numbering: "1. ...", "1) ...", "#1 ..."
            clean = line
            for prefix_len in range(1, 5):
                if len(line) > prefix_len and line[prefix_len] in ".):- ":
                    if line[:prefix_len].strip().isdigit():
                        clean = line[prefix_len + 1:].strip()
                        break
            if clean.startswith("#"):
                clean = clean.lstrip("#").strip()
                for prefix_len in range(1, 4):
                    if len(clean) > prefix_len and clean[prefix_len] in ".):- ":
                        if clean[:prefix_len].strip().isdigit():
                            clean = clean[prefix_len + 1:].strip()
                            break

            if len(clean) > 15:
                posts.append({
                    "type": agent_type["name"],
                    "count": agent_type["count"],
                    "text": clean[:300],
                    "round": round_num,
                })

        return posts[:n_posts]

    def _score_conversation(self, all_posts: list[dict], market_context: str) -> dict:
        """Analyze the full 500-agent conversation for contagion dynamics."""
        # Group posts by type for summary
        by_type = {}
        for p in all_posts:
            t = p["type"]
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(p)

        # Build conversation summary
        conv_parts = []
        for agent_type in AGENT_TYPES:
            name = agent_type["name"]
            count = agent_type["count"]
            posts = by_type.get(name, [])
            if posts:
                post_text = "\n".join(f"  - {p['text'][:150]}" for p in posts)
                conv_parts.append(f"[{name}] ({count} agents, {len(posts)} posts):\n{post_text}")

        conversation_text = "\n\n".join(conv_parts)

        prompt = f"""Analyze this 500-agent BTC investor simulation for panic contagion dynamics.

Market: {market_context[:300]}

Conversation across {NUM_ROUNDS} rounds:
{conversation_text}

Analyze contagion: Did fear spread from KOLs/leveraged traders to retail/newbies?
Did institutions/OGs stabilize or get infected? How did sentiment shift across rounds?

Output ONLY this JSON:
{{"overall_score": <0-100, 0=extreme fear, 100=extreme greed>, "contagion_effect": "<amplified|dampened|neutral>", "agents": [{{"name": "<type>", "panic_level": <0-100>, "reasoning": "<1 sentence>"}}]}}"""

        try:
            text = self.llm.call(prompt, temperature=0.1, max_tokens=2000)
            if not text or text == "(no response)":
                print("[Stage 2] Scoring: no response from LLM")
                return None

            start = text.find("{")
            end = text.rfind("}") + 1
            if start < 0 or end <= start:
                print(f"[Stage 2] Scoring: no JSON found in response ({len(text)} chars)")
                print(f"[Stage 2] Response preview: {text[:200]}")
                return None

            json_str = text[start:end]
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError:
                # Try to repair truncated JSON: close open arrays/objects
                repaired = json_str
                if repaired.count("[") > repaired.count("]"):
                    # Truncated inside agents array — close it
                    last_brace = repaired.rfind("}")
                    if last_brace > 0:
                        repaired = repaired[:last_brace + 1] + "]}"
                data = json.loads(repaired)
            contagion = data.get("contagion_effect", "neutral")
            score = data.get("overall_score", 50)
            print(f"[Stage 2] Contagion: {contagion} | Score: {score}/100")

            return {
                "sentiment_score": score,
                "agent_responses": data.get("agents", []),
                "contagion_effect": contagion,
            }

        except json.JSONDecodeError as e:
            print(f"[Stage 2] JSON parse error: {e}")
            print(f"[Stage 2] Raw: {text[start:start+300] if 'text' in dir() else 'N/A'}")
            return None
        except Exception as e:
            print(f"[Stage 2] Scoring error: {e}")
            return None
