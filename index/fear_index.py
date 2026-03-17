"""BTC Fear Index calculator.

Combines traditional market metrics (60%) with two-stage MiroFish
sentiment analysis + multi-agent simulation (40%).
"""

from config.settings import WEIGHTS


LABELS = [
    (0, 24, "Extreme Fear"),
    (25, 49, "Fear"),
    (50, 50, "Neutral"),
    (51, 74, "Greed"),
    (75, 100, "Extreme Greed"),
]


def calculate_fear_index(market_scores: dict, sentiment_score: float) -> dict:
    components = {
        "volatility": {
            "score": market_scores.get("volatility", 50),
            "weight": WEIGHTS["volatility"],
        },
        "momentum": {
            "score": market_scores.get("momentum", 50),
            "weight": WEIGHTS["momentum"],
        },
        "dominance": {
            "score": market_scores.get("dominance", 50),
            "weight": WEIGHTS["dominance"],
        },
        "mirofish_sentiment": {
            "score": sentiment_score,
            "weight": WEIGHTS["mirofish_sentiment"],
        },
    }

    total = sum(c["score"] * c["weight"] for c in components.values())
    total_weight = sum(c["weight"] for c in components.values())
    index_value = round(total / total_weight, 1)

    label = "Neutral"
    for low, high, name in LABELS:
        if low <= index_value <= high:
            label = name
            break

    return {
        "value": index_value,
        "label": label,
        "components": components,
    }


def format_report(
    index_result: dict,
    sim_result: dict = None,
) -> str:
    """Format a full human-readable report with Stage 1 + Stage 2 details."""
    v = index_result["value"]
    label = index_result["label"]
    components = index_result["components"]

    bar_len = 40
    filled = int(v / 100 * bar_len)
    bar = "█" * filled + "░" * (bar_len - filled)

    lines = [
        "",
        "╔══════════════════════════════════════════════════════════╗",
        "║        BTC FEAR & GREED INDEX (MiroFish Edition)         ║",
        "╠══════════════════════════════════════════════════════════╣",
        f"║  Score: {v:>5.1f} / 100    [{label:^16s}]              ║",
        f"║  [{bar}]        ║",
        "╠══════════════════════════════════════════════════════════╣",
        "║  Components:                                             ║",
    ]

    for name, data in components.items():
        score = data["score"]
        weight = data["weight"] * 100
        display_name = name.replace("_", " ").title()
        lines.append(
            f"║    {display_name:<25s} {score:>5.1f}  (w={weight:.0f}%)         ║"
        )

    lines.append("╠══════════════════════════════════════════════════════════╣")

    if sim_result:
        # Stage breakdown
        s1 = sim_result.get("stage1_score")
        s2 = sim_result.get("stage2_score")
        method = sim_result.get("method", "unknown")
        n_posts = sim_result.get("num_posts_analyzed", 0)

        lines.append(f"║  Method: {method:<46s} ║")
        lines.append(f"║  Posts analyzed: {n_posts:>6,d}                                ║")

        if s1 is not None:
            lines.append(f"║  Stage 1 (statistical):  {s1:>5.1f}                          ║")
        if s2 is not None:
            lines.append(f"║  Stage 2 (simulation):   {s2:>5.1f}                          ║")

        # Sentiment distribution
        ss = sim_result.get("sentiment_stats", {})
        if ss:
            lines.append("║                                                          ║")
            lines.append("║  Sentiment Distribution:                                 ║")
            for lbl, key in [
                ("Extreme Fear", "extreme_fear_pct"),
                ("Fear", "fear_pct"),
                ("Neutral", "neutral_pct"),
                ("Greed", "greed_pct"),
                ("Extreme Greed", "extreme_greed_pct"),
            ]:
                pct = ss.get(key, 0)
                mini_bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
                lines.append(f"║    {lbl:<14s} [{mini_bar}] {pct:>5.1f}%    ║")

        # Contagion effect
        contagion = None
        for r in sim_result.get("agent_responses", []):
            pass  # just checking

        # OASIS stats
        oasis = sim_result.get("oasis_stats", {})
        if oasis:
            lines.append("║                                                          ║")
            lines.append(
                f"║  OASIS: {oasis.get('total_posts', 0)} posts, "
                f"{oasis.get('total_comments', 0)} comments, "
                f"{oasis.get('total_actions', 0)} actions"
                f"              ║"
            )

    lines.append("╚══════════════════════════════════════════════════════════╝")

    # Agent breakdown
    agent_responses = sim_result.get("agent_responses", []) if sim_result else []
    if agent_responses:
        lines.append("")
        lines.append("Agent Simulation Breakdown (panic contagion analysis):")
        lines.append("-" * 58)
        for agent in sorted(agent_responses, key=lambda a: a.get("panic_level", 0), reverse=True):
            name = agent.get("name", "Unknown")
            panic = agent.get("panic_level", 0)
            reason = agent.get("reasoning", "")
            emoji = "🔴" if panic > 70 else "🟡" if panic > 40 else "🟢"
            lines.append(f"  {emoji} {name:<28s} Panic: {panic:>3.0f}/100")
            if reason:
                lines.append(f"     └─ {reason}")

    return "\n".join(lines)
