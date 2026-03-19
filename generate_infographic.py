"""Generate daily BTC Fear & Greed infographic.

Accepts dynamic pipeline result data. Designed for Twitter (1080x1080 square).
"""

import json
import os
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, Arc
import numpy as np


# ── Color system (not AI-slop cyan/purple) ──
BG = "#0a0f1a"
SURFACE = "#111827"
TEXT_PRIMARY = "#e2e8f0"
TEXT_MUTED = "#64748b"
TEXT_DIM = "#334155"
ACCENT_BLUE = "#3b82f6"

# Score colors: 4 discrete levels
COLOR_EXTREME_FEAR = "#ef4444"
COLOR_FEAR = "#f59e0b"
COLOR_NEUTRAL = "#94a3b8"
COLOR_GREED = "#34d399"
COLOR_EXTREME_GREED = "#10b981"

# Agent panic dot colors
DOT_HIGH = "#ef4444"
DOT_MID = "#f59e0b"
DOT_LOW = "#34d399"


def _score_color(score: float) -> str:
    if score < 25:
        return COLOR_EXTREME_FEAR
    elif score < 50:
        return COLOR_FEAR
    elif score == 50:
        return COLOR_NEUTRAL
    elif score < 75:
        return COLOR_GREED
    else:
        return COLOR_EXTREME_GREED


def _panic_color(level: int) -> str:
    if level > 60:
        return DOT_HIGH
    elif level > 35:
        return DOT_MID
    else:
        return DOT_LOW


def generate_infographic(result: dict, output_path: str = None) -> str:
    """Generate infographic from pipeline result dict.

    Args:
        result: Full pipeline result (same schema as result_v3.json)
        output_path: Where to save. Defaults to output/infographic_YYYY-MM-DD.png

    Returns:
        Path to saved image.
    """
    # ── Extract data ──
    index = result.get("index", {})
    score = index.get("value", 50)
    label = index.get("label", "Neutral")
    components = index.get("components", {})

    sim = result.get("simulation", {})
    agents = sim.get("agents", [])
    posts_analyzed = sim.get("posts_analyzed", 0)
    method = sim.get("method", "unknown")

    market = result.get("market_raw", {})
    price = market.get("price_usd", 0)
    change = market.get("change_24h_pct", 0)
    dominance = market.get("btc_dominance", 0)

    timestamp = result.get("timestamp", datetime.now(timezone.utc).isoformat())
    try:
        dt = datetime.fromisoformat(timestamp)
    except (ValueError, TypeError):
        dt = datetime.now(timezone.utc)
    date_str = dt.strftime("%b %d, %Y")

    score_col = _score_color(score)

    # ── Figure setup (1080x1080 at 2x) ──
    fig = plt.figure(figsize=(10.8, 10.8), facecolor=BG, dpi=200)

    # ── 1. Header: date + branding ──
    fig.text(0.08, 0.94, date_str.upper(), fontsize=11, color=TEXT_MUTED,
             fontfamily="sans-serif", fontweight="medium")
    fig.text(0.92, 0.94, "MiroFish", fontsize=11, color=ACCENT_BLUE,
             fontfamily="sans-serif", fontweight="bold", ha="right")
    fig.text(0.92, 0.92, "BTC Fear & Greed Index", fontsize=8, color=TEXT_DIM,
             fontfamily="sans-serif", ha="right")

    # ── 2. Hero gauge ──
    ax_gauge = fig.add_axes([0.15, 0.66, 0.7, 0.24])
    ax_gauge.set_xlim(-1.4, 1.4)
    ax_gauge.set_ylim(-0.1, 1.35)
    ax_gauge.set_facecolor(BG)
    ax_gauge.set_aspect("equal")
    ax_gauge.axis("off")

    # Background arc
    arc_bg = Arc((0, 0), 2.0, 2.0, angle=0, theta1=0, theta2=180,
                 color=TEXT_DIM, linewidth=14, alpha=0.2)
    ax_gauge.add_patch(arc_bg)

    # Colored arc segments
    segments = [
        (0, 45, COLOR_EXTREME_FEAR),
        (45, 90, COLOR_FEAR),
        (90, 135, COLOR_GREED),
        (135, 180, COLOR_EXTREME_GREED),
    ]
    for s_start, s_end, color in segments:
        arc = Arc((0, 0), 2.0, 2.0, angle=0, theta1=s_start, theta2=s_end,
                  color=color, linewidth=14, alpha=0.45)
        ax_gauge.add_patch(arc)

    # Needle
    angle_deg = 180 - (score / 100) * 180
    angle_rad = np.radians(angle_deg)
    nx = 0.82 * np.cos(angle_rad)
    ny = 0.82 * np.sin(angle_rad)
    ax_gauge.plot([0, nx], [0, ny], color=score_col, linewidth=3.5,
                  solid_capstyle="round", zorder=4)
    ax_gauge.plot(0, 0, "o", color=score_col, markersize=10, zorder=5)

    # Arc labels
    ax_gauge.text(-1.18, -0.02, "0", fontsize=9, color=COLOR_EXTREME_FEAR,
                  ha="center", fontfamily="sans-serif")
    ax_gauge.text(1.18, -0.02, "100", fontsize=9, color=COLOR_EXTREME_GREED,
                  ha="center", fontfamily="sans-serif")

    # ── 3. Score + label + price (stacked below gauge) ──
    fig.text(0.5, 0.635, f"{score:.0f}", fontsize=64, fontweight="bold",
             color=score_col, ha="center", va="top", fontfamily="monospace")
    fig.text(0.5, 0.575, label.upper(), fontsize=20, fontweight="bold",
             color=score_col, ha="center", va="top", fontfamily="sans-serif",
             alpha=0.9)

    change_sign = "+" if change >= 0 else ""
    fig.text(0.5, 0.545, f"BTC ${price:,.0f}  ({change_sign}{change:.1f}%)  |  Dom {dominance:.1f}%",
             fontsize=10, color=TEXT_MUTED, ha="center", va="top",
             fontfamily="sans-serif")

    # ── 4. Components row (dynamic) ──
    # Display names for components
    _COMP_LABELS = {
        "volatility": "Volatility",
        "momentum": "Momentum",
        "dominance": "Dominance",
        "derivatives": "Derivatives",
        "onchain": "On-chain",
        "mirofish_sentiment": "Sentiment",
        "google_trends": "Trends",
    }

    comp_items = []
    for key, data in components.items():
        label = _COMP_LABELS.get(key, key.replace("_", " ").title())
        w_pct = f"{data['weight'] * 100:.0f}%"
        comp_items.append((label, data["score"], w_pct))

    n_cols = len(comp_items)
    ax_comp = fig.add_axes([0.04, 0.46, 0.92, 0.06])
    ax_comp.set_facecolor(BG)
    ax_comp.axis("off")
    ax_comp.set_xlim(0, n_cols)
    ax_comp.set_ylim(0, 1)

    for i, (name, comp_score, weight) in enumerate(comp_items):
        x = i + 0.5
        comp_col = _score_color(comp_score)
        fontsize_name = 7 if n_cols > 5 else 8
        fontsize_score = 13 if n_cols > 5 else 15
        ax_comp.text(x, 0.9, name, fontsize=fontsize_name, color=TEXT_MUTED,
                     ha="center", fontfamily="sans-serif")
        ax_comp.text(x, 0.35, f"{comp_score:.0f}", fontsize=fontsize_score,
                     fontweight="bold", color=comp_col, ha="center",
                     fontfamily="monospace")
        ax_comp.text(x, 0.0, weight, fontsize=6, color=TEXT_DIM,
                     ha="center", fontfamily="sans-serif")

    # Divider
    line1 = matplotlib.lines.Line2D([0.08, 0.92], [0.45, 0.45], color=TEXT_DIM,
                                     linewidth=0.5, transform=fig.transFigure)
    fig.add_artist(line1)

    # ── 5. Agent panic breakdown ──
    if agents:
        sorted_agents = sorted(agents, key=lambda a: a.get("panic_level", 0), reverse=True)
        display_agents = sorted_agents[:4]
        calmest = sorted_agents[-1]
        if calmest not in display_agents:
            display_agents.append(calmest)

        n_agents = len(display_agents)
        ax_agents = fig.add_axes([0.08, 0.12, 0.84, 0.30])
        ax_agents.set_facecolor(BG)
        ax_agents.axis("off")
        ax_agents.set_xlim(0, 100)
        ax_agents.set_ylim(-0.8, n_agents + 0.8)

        ax_agents.text(0, n_agents + 0.4, "Agent Contagion Analysis",
                       fontsize=12, color=TEXT_PRIMARY, fontweight="bold",
                       fontfamily="sans-serif", va="bottom")
        ax_agents.text(100, n_agents + 0.4, "500 agents  |  5 rounds",
                       fontsize=8, color=TEXT_MUTED, fontfamily="sans-serif",
                       ha="right", va="bottom")

        for i, agent in enumerate(display_agents):
            y = n_agents - 1 - i
            name = agent.get("name", "Unknown")
            panic = agent.get("panic_level", 50)
            reasoning = agent.get("reasoning", "")
            dot_col = _panic_color(panic)

            # Dot
            ax_agents.plot(2, y, "o", color=dot_col, markersize=8, zorder=5)

            # Name
            ax_agents.text(5, y + 0.08, name, fontsize=10, color=TEXT_PRIMARY,
                           fontfamily="sans-serif", va="center")

            # Bar
            bar_width = panic * 0.55
            rect = FancyBboxPatch((38, y - 0.15), bar_width, 0.3,
                                   boxstyle="round,pad=0.05",
                                   facecolor=dot_col, alpha=0.3,
                                   edgecolor="none")
            ax_agents.add_patch(rect)

            # Score
            ax_agents.text(38 + bar_width + 2, y, f"{panic}",
                           fontsize=11, fontweight="bold", color=dot_col,
                           fontfamily="monospace", va="center")

            # Short reasoning (truncate)
            if reasoning:
                short = reasoning[:60] + ("..." if len(reasoning) > 60 else "")
                ax_agents.text(5, y - 0.28, short, fontsize=6.5,
                               color=TEXT_MUTED, fontfamily="sans-serif", va="center")

    # ── 6. Footer ──
    line2 = matplotlib.lines.Line2D([0.08, 0.92], [0.10, 0.10], color=TEXT_DIM,
                                     linewidth=0.5, transform=fig.transFigure)
    fig.add_artist(line2)

    footer_parts = []
    if posts_analyzed:
        footer_parts.append(f"{posts_analyzed:,} posts analyzed")
    footer_parts.append("500 AI agents")
    footer_parts.append("OASIS engine")
    footer_text = "  |  ".join(footer_parts)
    fig.text(0.5, 0.07, footer_text, fontsize=9, color=TEXT_MUTED,
             ha="center", fontfamily="sans-serif")

    fig.text(0.5, 0.04, "github.com/robin-ph/btc-fear-greed-index",
             fontsize=8, color=ACCENT_BLUE, ha="center", fontfamily="sans-serif")

    # ── Save ──
    if output_path is None:
        os.makedirs("output", exist_ok=True)
        date_slug = dt.strftime("%Y-%m-%d")
        output_path = f"output/infographic_{date_slug}.png"

    plt.savefig(output_path, dpi=200, bbox_inches="tight",
                facecolor=BG, pad_inches=0.3)
    plt.close(fig)
    print(f"[Infographic] Saved: {output_path}")
    return output_path


# ── CLI: generate from existing result JSON ──
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        result_file = sys.argv[1]
    else:
        # Try latest result file
        for f in ["result_v3.json", "result_v2.json", "result.json"]:
            if os.path.exists(f):
                result_file = f
                break
        else:
            print("Usage: python generate_infographic.py <result.json>")
            sys.exit(1)

    with open(result_file) as f:
        result = json.load(f)

    path = generate_infographic(result)
    print(f"Done: {path}")
