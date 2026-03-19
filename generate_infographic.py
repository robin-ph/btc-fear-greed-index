"""Generate daily BTC Fear & Greed infographic.

Minimalist white design. Three focal points: score, price, date.
"""

import json
import os
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import numpy as np


# ── Color system ──
BG = "#ffffff"
TEXT_BLACK = "#1a1a1a"
TEXT_GRAY = "#6b7280"
TEXT_LIGHT = "#9ca3af"
DIVIDER = "#e5e7eb"

# Score colors
C_EXTREME_FEAR = "#dc2626"
C_FEAR = "#ea580c"
C_NEUTRAL = "#6b7280"
C_GREED = "#16a34a"
C_EXTREME_GREED = "#15803d"

# Gauge arc colors
ARC_FEAR = "#fca5a5"
ARC_MILD_FEAR = "#fdba74"
ARC_NEUTRAL = "#d1d5db"
ARC_MILD_GREED = "#86efac"
ARC_GREED = "#6ee7b7"


def _score_color(score: float) -> str:
    if score < 25: return C_EXTREME_FEAR
    elif score < 45: return C_FEAR
    elif score <= 55: return C_NEUTRAL
    elif score < 75: return C_GREED
    else: return C_EXTREME_GREED


def generate_infographic(result: dict, output_path: str = None) -> str:
    index = result.get("index", {})
    score = index.get("value", 50)
    label = index.get("label", "Neutral")

    market = result.get("market_raw", {})
    price = market.get("price_usd", 0)
    change = market.get("change_24h_pct", 0)

    timestamp = result.get("timestamp", datetime.now(timezone.utc).isoformat())
    try:
        dt = datetime.fromisoformat(timestamp)
    except (ValueError, TypeError):
        dt = datetime.now(timezone.utc)

    date_str = dt.strftime("%b %d, %Y")
    score_col = _score_color(score)
    change_sign = "+" if change >= 0 else ""

    # ── Figure: 1080x1080 ──
    fig = plt.figure(figsize=(10.8, 10.8), facecolor=BG, dpi=200)

    # ── Date (prominent, top center) ──
    fig.text(0.5, 0.90, date_str, fontsize=16, color=TEXT_GRAY,
             fontfamily="sans-serif", ha="center")

    # ── Hero: Score number (massive, centered) ──
    fig.text(0.5, 0.66, f"{score:.0f}", fontsize=180, fontweight="bold",
             color=score_col, ha="center", va="center", fontfamily="sans-serif")

    # ── Label below score ──
    fig.text(0.5, 0.50, label.upper(), fontsize=30, fontweight="bold",
             color=score_col, ha="center", va="center", fontfamily="sans-serif")

    # ── Thin gauge bar (minimal) ──
    ax_bar = fig.add_axes([0.2, 0.46, 0.6, 0.015])
    ax_bar.set_xlim(0, 100)
    ax_bar.set_ylim(0, 1)
    ax_bar.axis("off")

    # Gradient segments
    bar_segs = [
        (0, 25, C_EXTREME_FEAR, 0.25),
        (25, 45, C_FEAR, 0.25),
        (45, 55, C_NEUTRAL, 0.2),
        (55, 75, C_GREED, 0.25),
        (75, 100, C_EXTREME_GREED, 0.25),
    ]
    for x0, x1, color, alpha in bar_segs:
        ax_bar.barh(0.5, x1 - x0, left=x0, height=1, color=color, alpha=alpha)

    # Needle marker
    ax_bar.plot(score, 0.5, "v", color=score_col, markersize=12, zorder=5)

    # ── BTC Price (clean, below gauge) ──
    fig.text(0.5, 0.39, f"BTC ${price:,.0f}", fontsize=22,
             color=TEXT_BLACK, ha="center", fontfamily="sans-serif", fontweight="medium")

    change_color = C_GREED if change >= 0 else C_EXTREME_FEAR
    fig.text(0.5, 0.355, f"{change_sign}{change:.1f}%", fontsize=14,
             color=change_color, ha="center", fontfamily="sans-serif")

    # ── Divider ──
    line = matplotlib.lines.Line2D([0.25, 0.75], [0.31, 0.31],
                                    color=DIVIDER, linewidth=0.8,
                                    transform=fig.transFigure)
    fig.add_artist(line)

    # ── Brand (bottom, subtle) ──
    fig.text(0.5, 0.12, "Built by @whataidoing",
             fontsize=10, color=TEXT_LIGHT, ha="center", fontfamily="sans-serif")

    # ── Save ──
    if output_path is None:
        os.makedirs("output", exist_ok=True)
        date_slug = dt.strftime("%Y-%m-%d")
        output_path = f"output/infographic_{date_slug}.png"

    plt.savefig(output_path, dpi=200, bbox_inches="tight",
                facecolor=BG, pad_inches=0.5)
    plt.close(fig)
    print(f"[Infographic] Saved: {output_path}")
    return output_path


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        result_file = sys.argv[1]
    else:
        for f in ["results/2026-03-19.json", "result_v3.json", "result.json"]:
            if os.path.exists(f):
                result_file = f
                break
        else:
            print("Usage: python generate_infographic.py <result.json>")
            sys.exit(1)

    with open(result_file) as f:
        result = json.load(f)
    generate_infographic(result)
