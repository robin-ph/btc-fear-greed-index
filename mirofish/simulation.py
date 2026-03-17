"""Two-stage MiroFish sentiment simulation.

Stage 1: Statistical analysis of ALL scraped posts (VADER + engagement weighting)
Stage 2: OASIS multi-agent simulation using Stage 1 results as initial conditions
         Claude scores the simulation output for final fear/greed assessment
"""

import json
import subprocess
import os
from dataclasses import asdict

from analysis.sentiment import SentimentAnalyzer, SentimentStats, format_sentiment_report


class MiroFishSimulator:
    def __init__(self):
        self.analyzer = SentimentAnalyzer()

    def run_simulation(
        self, social_posts: list[dict], market_data: dict
    ) -> dict:
        """Two-stage pipeline: statistical analysis → OASIS simulation."""

        # === Stage 1: Analyze ALL posts ===
        print(f"\n[Stage 1] Analyzing {len(social_posts)} posts with VADER+crypto lexicon...")
        stats = self.analyzer.analyze_all(social_posts)
        print(format_sentiment_report(stats))

        stage1_score = stats.to_fear_score()
        print(f"[Stage 1] Base fear score: {stage1_score:.1f}/100")

        # === Stage 2: OASIS simulation ===
        oasis_result = self._run_oasis(stats, market_data)

        if oasis_result and oasis_result.get("agent_generated_content"):
            # Score OASIS output with Claude
            stage2_result = self._score_with_claude(oasis_result, market_data, stats)
            stage2_score = stage2_result.get("sentiment_score", stage1_score)

            # Final score: blend Stage 1 (statistical) and Stage 2 (simulation)
            # Stage 1 = 40% (grounded in data), Stage 2 = 60% (simulation adds contagion)
            final_score = stage1_score * 0.4 + stage2_score * 0.6

            return {
                "sentiment_score": round(final_score, 2),
                "stage1_score": stage1_score,
                "stage2_score": stage2_score,
                "agent_responses": stage2_result.get("agent_responses", []),
                "method": "oasis_simulation",
                "num_posts_analyzed": stats.analyzed_posts,
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
                "oasis_stats": {
                    "total_posts": oasis_result.get("total_posts", 0),
                    "total_comments": oasis_result.get("total_comments", 0),
                    "total_actions": oasis_result.get("total_actions", 0),
                    "agent_content": len(oasis_result.get("agent_generated_content", [])),
                },
            }

        # Fallback: Stage 1 only
        print("[Stage 2] OASIS failed, using Stage 1 score only")
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

    def _run_oasis(self, stats: SentimentStats, market_data: dict) -> dict:
        """Run OASIS in mirofish conda env with Stage 1 stats as input."""
        try:
            import tempfile

            # Serialize stats for OASIS
            stats_dict = {
                "analyzed_posts": stats.analyzed_posts,
                "mean_score": stats.mean_score,
                "median_score": stats.median_score,
                "extreme_fear_ratio": stats.extreme_fear_ratio,
                "fear_ratio": stats.fear_ratio,
                "neutral_ratio": stats.neutral_ratio,
                "greed_ratio": stats.greed_ratio,
                "extreme_greed_ratio": stats.extreme_greed_ratio,
                "representative_posts": stats.representative_posts[:50],
                "top_fear_posts": stats.top_fear_posts[:10],
                "top_greed_posts": stats.top_greed_posts[:10],
            }

            inputs = {
                "sentiment_stats": stats_dict,
                "market_data": market_data,
                "max_rounds": 5,
            }
            input_file = tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False, dir="/tmp"
            )
            json.dump(inputs, input_file, ensure_ascii=False)
            input_file.close()

            output_file = input_file.name.replace(".json", "_output.json")
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

            script = f"""
import sys
sys.path.insert(0, '{project_root}')
import json
import asyncio
from mirofish.oasis_runner import OasisSimulator

with open('{input_file.name}') as f:
    inputs = json.load(f)

simulator = OasisSimulator()
result = asyncio.run(simulator.run_simulation(
    inputs['sentiment_stats'],
    inputs['market_data'],
    inputs['max_rounds'],
))

with open('{output_file}', 'w') as f:
    json.dump(result, f, ensure_ascii=False)

print('OASIS simulation complete')
"""
            result = subprocess.run(
                ["conda", "run", "-n", "mirofish", "python", "-c", script],
                capture_output=True,
                text=True,
                timeout=3600,
                cwd=project_root,
            )

            if result.returncode != 0:
                print(f"[OASIS] Error: {result.stderr[:500]}")
                return None

            with open(output_file) as f:
                oasis_result = json.load(f)

            content_count = len(oasis_result.get("agent_generated_content", []))
            posts = oasis_result.get("total_posts", 0)
            comments = oasis_result.get("total_comments", 0)
            print(f"[OASIS] Generated {content_count} content pieces ({posts} posts, {comments} comments)")
            return oasis_result

        except Exception as e:
            print(f"[OASIS] Failed: {e}")
            return None

    def _score_with_claude(self, oasis_result: dict, market_data: dict, stats: SentimentStats) -> dict:
        """Use Claude to analyze OASIS output combined with Stage 1 stats."""
        content = oasis_result.get("agent_generated_content", [])

        content_text = "\n".join(
            f"- [Agent {c['user_id']}, {c['type']}] {c['text'][:200]}"
            for c in content[:50]
        )

        raw = market_data.get("raw", {})
        prompt = f"""You are analyzing a multi-agent BTC investor simulation that was seeded with
real-world social media sentiment data.

STATISTICAL CONTEXT (from analyzing {stats.analyzed_posts:,d} real social media posts):
- Overall sentiment: {stats.mean_score:.1f}/100 (0=extreme fear, 100=extreme greed)
- Extreme Fear posts: {stats.extreme_fear_ratio * 100:.1f}%
- Fear posts: {stats.fear_ratio * 100:.1f}%
- Neutral: {stats.neutral_ratio * 100:.1f}%
- Greed: {stats.greed_ratio * 100:.1f}%
- Extreme Greed: {stats.extreme_greed_ratio * 100:.1f}%

MARKET: BTC ${raw.get('price_usd', 0):,.0f}, 24h {raw.get('change_24h_pct', 0):.2f}%

SIMULATION OUTPUT (8 agents interacting on simulated Reddit):
{content_text}

Analyze the simulation: how did fear/greed SPREAD between agents?
Did panic-prone agents infect calmer ones? Did HODLers stabilize sentiment?

Output JSON only:
{{"overall_score": <0-100 fear score>, "contagion_effect": <"amplified"|"dampened"|"neutral">, "agents": [{{"name": "type", "panic_level": <0-100>, "reasoning": "1 sentence"}}]}}
"""

        try:
            result = subprocess.run(
                ["claude", "-p", "--output-format", "text"],
                input=prompt,
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode != 0:
                return {"sentiment_score": stats.to_fear_score(), "agent_responses": []}

            text = result.stdout.strip()
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(text[start:end])
                contagion = data.get("contagion_effect", "neutral")
                print(f"[Stage 2] Contagion effect: {contagion}")
                return {
                    "sentiment_score": data.get("overall_score", 50),
                    "agent_responses": data.get("agents", []),
                    "contagion_effect": contagion,
                }

        except Exception as e:
            print(f"[Stage 2] Scoring error: {e}")

        return {"sentiment_score": stats.to_fear_score(), "agent_responses": []}
