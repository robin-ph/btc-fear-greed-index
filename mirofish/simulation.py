"""Two-stage MiroFish sentiment pipeline (OpenRouter API).

Stage 1: Mega-batch sentiment scoring via Nemotron
Stage 2: 10-agent multi-round REAL conversation simulation
         Each agent reads previous round's posts and responds — genuine emergence

Total API calls: ~3 (Stage 1) + ~30 (Stage 2: 10 agents × 3 rounds) = ~33
All free via NVIDIA Nemotron on OpenRouter.
"""

import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from openai import OpenAI

from analysis.sentiment import SentimentAnalyzer, SentimentStats, format_sentiment_report

# ── Config ──
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3-super-120b-a12b:free")

NUM_AGENTS = 10
NUM_ROUNDS = 3
AGENT_CONCURRENCY = 3  # Conservative: free model limits 16 req/min


# ── 10 representative agent types ──
AGENT_PROFILES = [
    {
        "name": "Retail Panic Seller",
        "system": (
            "You are a retail crypto investor who bought BTC at $71,000. You're down significantly "
            "and extremely anxious. You check prices every 5 minutes. You're prone to panic selling "
            "and heavily influenced by fear narratives on social media. Write SHORT posts (1-3 sentences) "
            "reacting to what you see. Be emotional and authentic."
        ),
    },
    {
        "name": "Pure Newbie",
        "system": (
            "You are a complete crypto newbie who bought BTC last month after hearing about it on TikTok. "
            "You have no understanding of market cycles. Any red day makes you question everything. "
            "Write SHORT posts (1-3 sentences). Ask naive questions, express confusion and worry."
        ),
    },
    {
        "name": "Leveraged Degen",
        "system": (
            "You are a leveraged crypto trader running 20x long on BTC futures. A 5% drop means "
            "liquidation. You're always watching liquidation levels and funding rates. "
            "Write SHORT posts (1-3 sentences). Be intense, talk about leverage, liquidation risk."
        ),
    },
    {
        "name": "Crypto KOL",
        "system": (
            "You are a crypto influencer with 500K followers. You amplify whatever narrative gets "
            "engagement — bearish during dumps, bullish during pumps. You use dramatic language. "
            "Write SHORT posts (1-3 sentences). Be sensational, use crypto slang."
        ),
    },
    {
        "name": "Technical Analyst",
        "system": (
            "You are a technical analyst who trades based on chart patterns, support/resistance, "
            "and momentum indicators. You're relatively objective but lean bearish in downtrends. "
            "Write SHORT posts (1-3 sentences). Reference specific technical levels."
        ),
    },
    {
        "name": "DeFi Degen",
        "system": (
            "You are a DeFi user with BTC as collateral in lending protocols. Your liquidation "
            "threshold is at $58,000. You monitor health factors obsessively. "
            "Write SHORT posts (1-3 sentences). Talk about collateral ratios and liquidation risk."
        ),
    },
    {
        "name": "Moderate Retail",
        "system": (
            "You are a retail investor with some crypto experience. You bought BTC at $45,000. "
            "You're in profit but worried about giving back gains. You try to be rational "
            "but get swayed by crowd sentiment. Write SHORT posts (1-3 sentences)."
        ),
    },
    {
        "name": "Miner Operator",
        "system": (
            "You are a BTC miner with break-even cost around $42,000. You care about hashrate, "
            "difficulty, energy costs, and whether mining remains profitable. "
            "Write SHORT posts (1-3 sentences). Provide mining perspective."
        ),
    },
    {
        "name": "Institutional Whale",
        "system": (
            "You are an institutional investor managing a crypto fund. You're data-driven and "
            "contrarian — you buy when retail panics. You look at on-chain data, macro indicators. "
            "Write SHORT posts (1-3 sentences). Be calm, analytical, contrarian."
        ),
    },
    {
        "name": "Diamond Hands OG",
        "system": (
            "You are a long-term BTC holder since 2017. You've survived 3 crashes of -80%. "
            "Nothing phases you. You believe in BTC fundamentals and see crashes as buying opportunities. "
            "Write SHORT posts (1-3 sentences). Be calm, dismissive of panic."
        ),
    },
]


class MiroFishSimulator:
    def __init__(self):
        self.analyzer = SentimentAnalyzer()
        self.client = OpenAI(
            api_key=OPENROUTER_API_KEY,
            base_url=OPENROUTER_BASE_URL,
        )
        self.model = OPENROUTER_MODEL

    def run_simulation(
        self, social_posts: list[dict], market_data: dict
    ) -> dict:
        """Two-stage pipeline: mega-batch analysis → multi-agent conversation."""

        # === Stage 1: Analyze ALL posts ===
        print(f"\n[Stage 1] Analyzing {len(social_posts)} posts via OpenRouter...")
        stats = self.analyzer.analyze_all(social_posts)
        print(format_sentiment_report(stats))

        stage1_score = stats.to_fear_score()
        print(f"[Stage 1] Base fear score: {stage1_score:.1f}/100")

        # === Stage 2: Multi-agent conversation ===
        stage2_result = self._run_agent_conversation(stats, market_data)

        if stage2_result:
            stage2_score = stage2_result.get("sentiment_score", stage1_score)
            final_score = stage1_score * 0.4 + stage2_score * 0.6

            return {
                "sentiment_score": round(final_score, 2),
                "stage1_score": stage1_score,
                "stage2_score": stage2_score,
                "agent_responses": stage2_result.get("agent_responses", []),
                "method": "multi_agent_conversation",
                "num_posts_analyzed": stats.analyzed_posts,
                "conversation_log": stage2_result.get("conversation_log", []),
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

        # Fallback: Stage 1 only
        print("[Stage 2] Agent conversation failed, using Stage 1 only")
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

    def _call_llm(self, system: str, user: str) -> str:
        """Single OpenRouter API call with retry + rate limit handling."""
        import time
        for attempt in range(3):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    temperature=0.8,
                    max_tokens=300,
                )
                content = response.choices[0].message.content
                if content:
                    return content.strip()
            except Exception as e:
                if "429" in str(e):
                    time.sleep(5 * (attempt + 1))  # 5s, 10s, 15s backoff
                    continue
            time.sleep(1)
        return "(no response)"

    def _run_agent_conversation(self, stats: SentimentStats, market_data: dict) -> dict:
        """Run 10 agents × 3 rounds of REAL conversation.

        Each round: all agents see previous round's posts → respond concurrently.
        This produces genuine emergent contagion dynamics.
        """
        raw = market_data.get("raw", {})

        # Build market context
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
            f"Social sentiment from {stats.analyzed_posts:,d} posts: "
            f"Fear {(stats.extreme_fear_ratio + stats.fear_ratio) * 100:.0f}% / "
            f"Neutral {stats.neutral_ratio * 100:.0f}% / "
            f"Greed {(stats.greed_ratio + stats.extreme_greed_ratio) * 100:.0f}%\n\n"
            f"Top fear posts from real social media:\n{fear_samples}\n\n"
            f"Top greed posts:\n{greed_samples}"
        )

        conversation_log = []
        all_posts = []  # Accumulates across rounds

        try:
            import time
            for round_num in range(1, NUM_ROUNDS + 1):
                if round_num > 1:
                    time.sleep(10)  # Rate limit buffer between rounds
                print(f"[Stage 2] Round {round_num}/{NUM_ROUNDS} "
                      f"({NUM_AGENTS} agents, {AGENT_CONCURRENCY} concurrent)...")

                # Build the forum thread for this round
                if round_num == 1:
                    forum_context = (
                        f"You're on a crypto Reddit forum. Here's today's market data:\n\n"
                        f"{market_context}\n\n"
                        f"React to this data. What's your take? Post on the forum."
                    )
                else:
                    # Agents see previous round's posts
                    recent_posts = "\n".join(
                        f"[{p['agent']}]: {p['text']}"
                        for p in all_posts[-(NUM_AGENTS * 2):]  # Last 2 rounds
                    )
                    forum_context = (
                        f"Market data:\n{market_context}\n\n"
                        f"Recent forum posts:\n{recent_posts}\n\n"
                        f"Respond to the discussion. Do you agree or disagree with what others are saying?"
                    )

                # Run all agents concurrently for this round
                round_posts = self._run_round(forum_context, round_num)
                all_posts.extend(round_posts)
                conversation_log.append({
                    "round": round_num,
                    "posts": round_posts,
                })

                # Print a sample
                for p in round_posts[:3]:
                    print(f"    [{p['agent']}]: {p['text'][:80]}...")

            # === Score the conversation ===
            print(f"[Stage 2] Scoring {len(all_posts)} agent posts...")
            result = self._score_conversation(all_posts, market_context)
            result["conversation_log"] = conversation_log
            return result

        except Exception as e:
            print(f"[Stage 2] Error: {e}")
            return None

    def _run_round(self, forum_context: str, round_num: int) -> list[dict]:
        """Run all agents for one round, concurrently."""
        posts = []

        with ThreadPoolExecutor(max_workers=AGENT_CONCURRENCY) as executor:
            futures = {
                executor.submit(
                    self._call_llm, agent["system"], forum_context
                ): agent
                for agent in AGENT_PROFILES
            }
            for future in as_completed(futures):
                agent = futures[future]
                try:
                    text = future.result()
                    # Clean up: take first 1-3 sentences
                    text = text.replace("\n", " ").strip()[:300]
                    posts.append({
                        "agent": agent["name"],
                        "text": text,
                        "round": round_num,
                    })
                except Exception as e:
                    posts.append({
                        "agent": agent["name"],
                        "text": f"[no response: {e}]",
                        "round": round_num,
                    })

        return posts

    def _score_conversation(self, all_posts: list[dict], market_context: str) -> dict:
        """Analyze the full conversation for contagion dynamics."""
        conversation_text = "\n".join(
            f"[Round {p['round']}, {p['agent']}]: {p['text'][:200]}"
            for p in all_posts
        )

        prompt = f"""Analyze this multi-agent BTC investor simulation conversation for panic contagion dynamics.

Market context:
{market_context}

Full conversation ({len(all_posts)} posts across {NUM_ROUNDS} rounds):
{conversation_text}

Analyze: How did fear/greed SPREAD between agents across rounds?
- Did panic-prone agents infect calmer ones?
- Did HODLers and institutions stabilize sentiment?
- Did KOLs amplify fear narratives?

Output ONLY this JSON:
{{"overall_score": <0-100 where 0=extreme fear, 100=extreme greed>, "contagion_effect": "<amplified|dampened|neutral>", "agents": [{{"name": "<agent name>", "panic_level": <0-100>, "reasoning": "<1 sentence>"}}]}}"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
            )
            text = response.choices[0].message.content.strip()

            start = text.find("{")
            end = text.rfind("}") + 1
            if start < 0 or end <= start:
                print(f"[Stage 2] No JSON in scoring response")
                return None

            data = json.loads(text[start:end])
            contagion = data.get("contagion_effect", "neutral")
            print(f"[Stage 2] Contagion: {contagion} | Score: {data.get('overall_score', 50)}/100")

            return {
                "sentiment_score": data.get("overall_score", 50),
                "agent_responses": data.get("agents", []),
                "contagion_effect": contagion,
            }

        except Exception as e:
            print(f"[Stage 2] Scoring error: {e}")
            return None
