"""OASIS multi-agent simulation with 500 diverse BTC investor agents.

Uses OASIS engine (camel-oasis) with OpenRouter API (NVIDIA Nemotron).
Agents interact on simulated Reddit, seeded with real social media
data from Stage 1 sentiment analysis.
"""

import asyncio
import json
import os
import sqlite3
import tempfile
from typing import Optional

from camel.models import ModelFactory
from camel.types import ModelPlatformType

from oasis import (
    make,
    generate_reddit_agent_graph,
    LLMAction,
    ManualAction,
    ActionType,
    DefaultPlatformType,
)

from mirofish.profile_generator import generate_profiles


NUM_AGENTS = 500


class OasisSimulator:
    """Run OASIS multi-agent BTC fear simulation via OpenRouter API."""

    def __init__(
        self,
        api_key: str = None,
        base_url: str = None,
        model_name: str = None,
        num_agents: int = NUM_AGENTS,
    ):
        api_key = api_key or os.getenv("OPENROUTER_API_KEY", "")
        base_url = base_url or os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        # Use Nano (30B) for agent simulation — fast + cheap, Super for scoring only
        model_name = model_name or os.getenv("OASIS_MODEL", "nvidia/nemotron-3-nano-30b-a3b")
        self.num_agents = num_agents
        self.model = ModelFactory.create(
            model_platform=ModelPlatformType.OPENAI_COMPATIBLE_MODEL,
            model_type=model_name,
            api_key=api_key,
            url=base_url,
            timeout=180,
        )

    async def run_simulation(
        self,
        sentiment_stats: dict,
        market_data: dict,
        max_rounds: int = 5,
        db_path: Optional[str] = None,
    ) -> dict:
        """Run full OASIS simulation with 500 agents."""
        sim_dir = tempfile.mkdtemp(prefix="btc_fear_sim_")
        profile_path = os.path.join(sim_dir, "profiles.json")
        if db_path is None:
            db_path = os.path.join(sim_dir, "simulation.db")

        # Generate diverse agent profiles
        print(f"[OASIS] Generating {self.num_agents} agent profiles...")
        profiles = generate_profiles(self.num_agents)
        with open(profile_path, "w") as f:
            json.dump(profiles, f, indent=2, ensure_ascii=False)

        print(f"[OASIS] Creating agent graph...")
        agent_graph = await generate_reddit_agent_graph(
            profile_path=profile_path,
            model=self.model,
            available_actions=[
                ActionType.CREATE_POST,
                ActionType.LIKE_POST,
                ActionType.DISLIKE_POST,
                ActionType.CREATE_COMMENT,
                ActionType.DO_NOTHING,
            ],
        )

        env = make(
            agent_graph=agent_graph,
            platform=DefaultPlatformType.REDDIT,
            database_path=db_path,
            semaphore=50,  # OpenRouter paid tier supports high concurrency
        )

        print("[OASIS] Resetting environment (signing up agents)...")
        await env.reset()

        # Seed with Stage 1 data
        seed_posts = self._build_seed_posts(sentiment_stats)
        print(f"[OASIS] Seeding {len(seed_posts)} posts from Stage 1...")
        await self._seed_posts(env, seed_posts, market_data, sentiment_stats)

        # Run simulation
        agent_pairs = agent_graph.get_agents()
        agents = [agent for _, agent in agent_pairs]
        print(f"[OASIS] Starting {max_rounds}-round simulation with {len(agents)} agents...")

        for round_num in range(1, max_rounds + 1):
            print(f"[OASIS] Round {round_num}/{max_rounds} ({len(agents)} agents)...")
            actions = {agent: LLMAction() for agent in agents}
            await env.step(actions)

        await env.close()
        print(f"[OASIS] Simulation complete. DB: {db_path}")

        result = self._analyze_simulation(db_path)
        result["sim_dir"] = sim_dir
        result["db_path"] = db_path
        result["num_agents"] = len(agents)
        return result

    def _build_seed_posts(self, sentiment_stats: dict) -> list[dict]:
        """Build seed posts from Stage 1 results."""
        seed = []
        for p in sentiment_stats.get("representative_posts", [])[:30]:
            seed.append(p)
        for p in sentiment_stats.get("top_fear_posts", [])[:10]:
            if p not in seed:
                seed.append(p)
        for p in sentiment_stats.get("top_greed_posts", [])[:10]:
            if p not in seed:
                seed.append(p)
        return seed[:50]

    async def _seed_posts(self, env, seed_posts, market_data, sentiment_stats):
        """Seed simulation with market context and representative posts."""
        agent_pairs = env.agent_graph.get_agents()
        agents = [agent for _, agent in agent_pairs]
        if not agents:
            return

        # Statistical summary post
        raw = market_data.get("raw", {})
        stats_summary = (
            f"BTC MARKET & SENTIMENT REPORT\n"
            f"Price: ${raw.get('price_usd', 0):,.0f} | 24h: {raw.get('change_24h_pct', 0):.2f}%\n"
            f"Dominance: {raw.get('btc_dominance', 0):.1f}% | Vol: ${raw.get('volume_24h_usd', 0):,.0f}\n\n"
            f"Analysis of {sentiment_stats.get('analyzed_posts', 0):,d} social media posts:\n"
            f"- Extreme Fear: {sentiment_stats.get('extreme_fear_ratio', 0) * 100:.1f}%\n"
            f"- Fear: {sentiment_stats.get('fear_ratio', 0) * 100:.1f}%\n"
            f"- Neutral: {sentiment_stats.get('neutral_ratio', 0) * 100:.1f}%\n"
            f"- Greed: {sentiment_stats.get('greed_ratio', 0) * 100:.1f}%\n"
            f"- Extreme Greed: {sentiment_stats.get('extreme_greed_ratio', 0) * 100:.1f}%"
        )

        await env.step({
            agents[0]: ManualAction(
                action_type=ActionType.CREATE_POST,
                action_args={"content": stats_summary},
            )
        })

        # Batch seed: combine posts into chunks to avoid 50 sequential steps
        chunk_size = 5
        for chunk_start in range(0, len(seed_posts), chunk_size):
            chunk = seed_posts[chunk_start:chunk_start + chunk_size]
            batch_actions = {}
            for j, post in enumerate(chunk):
                agent_idx = (chunk_start + j) % len(agents)
                text = post.get("text", "")[:400]
                source = post.get("source", "unknown")
                batch_actions[agents[agent_idx]] = ManualAction(
                    action_type=ActionType.CREATE_POST,
                    action_args={"content": f"[{source}] {text}"},
                )
            await env.step(batch_actions)

    def _analyze_simulation(self, db_path: str) -> dict:
        """Analyze simulation database."""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT user_id, content, num_likes, num_dislikes, created_at FROM post ORDER BY created_at"
        )
        posts = cursor.fetchall()

        cursor.execute("SELECT user_id, content, created_at FROM comment ORDER BY created_at")
        comments = cursor.fetchall()

        cursor.execute("SELECT * FROM trace ORDER BY created_at")
        traces = cursor.fetchall()

        conn.close()

        all_text = []
        for p in posts:
            if p[1] and not p[1].startswith("["):
                all_text.append({
                    "user_id": p[0],
                    "text": p[1],
                    "likes": p[2] or 0,
                    "dislikes": p[3] or 0,
                    "type": "post",
                })
        for c in comments:
            if c[1]:
                all_text.append({
                    "user_id": c[0],
                    "text": c[1],
                    "type": "comment",
                })

        # Action stats per agent
        action_stats = {}
        for t in traces:
            aid, action = t[0], t[2]
            if aid not in action_stats:
                action_stats[aid] = {}
            action_stats[aid][action] = action_stats[aid].get(action, 0) + 1

        return {
            "total_posts": len(posts),
            "total_comments": len(comments),
            "total_actions": len(traces),
            "agent_generated_content": all_text,
            "seeded_posts": len([p for p in posts if p[1] and p[1].startswith("[")]),
            "action_stats": action_stats,
        }


def run_oasis_simulation(
    sentiment_stats: dict,
    market_data: dict,
    max_rounds: int = 5,
) -> dict:
    """Sync entry point."""
    simulator = OasisSimulator()
    return asyncio.run(
        simulator.run_simulation(sentiment_stats, market_data, max_rounds)
    )
