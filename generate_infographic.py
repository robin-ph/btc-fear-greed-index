"""Generate Twitter infographic for BTC Fear & Greed Index article."""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import numpy as np

# Dark theme colors
BG = '#0d1117'
CARD_BG = '#161b22'
TEXT = '#e6edf3'
TEXT_DIM = '#8b949e'
ACCENT = '#58a6ff'
RED = '#f85149'
ORANGE = '#d29922'
GREEN = '#3fb950'
YELLOW = '#e3b341'
BORDER = '#30363d'

fig = plt.figure(figsize=(12, 18), facecolor=BG)

# ============================================================
# TITLE
# ============================================================
fig.text(0.5, 0.97, 'BTC Fear & Greed Index', fontsize=36, fontweight='bold',
         color=TEXT, ha='center', fontfamily='monospace')
fig.text(0.5, 0.955, 'MiroFish Edition', fontsize=16, color=ACCENT,
         ha='center', fontfamily='monospace')
fig.text(0.5, 0.940, '500 AI Agents  |  2,747 Posts  |  3 Platforms',
         fontsize=11, color=TEXT_DIM, ha='center', fontfamily='monospace')

# ============================================================
# SCORE GAUGE
# ============================================================
ax_gauge = fig.add_axes([0.1, 0.85, 0.8, 0.07])
ax_gauge.set_xlim(0, 100)
ax_gauge.set_ylim(0, 1)
ax_gauge.set_facecolor(BG)
ax_gauge.axis('off')

# Gradient bar
colors_bar = ['#f85149', '#f85149', '#d29922', '#d29922', '#e6edf3', '#3fb950', '#3fb950']
cmap = matplotlib.colors.LinearSegmentedColormap.from_list('fear', colors_bar)
gradient = np.linspace(0, 1, 256).reshape(1, -1)
ax_gauge.imshow(gradient, aspect='auto', cmap=cmap, extent=[0, 100, 0.15, 0.85],
                alpha=0.85)
ax_gauge.add_patch(plt.Rectangle((0, 0.15), 100, 0.7, fill=False,
                                  edgecolor=BORDER, linewidth=2, zorder=3))

# Score markers
score = 40.1
trad = 23

# Traditional marker
ax_gauge.plot([trad, trad], [0.15, 0.85], color=RED, linewidth=2.5,
              zorder=4, linestyle='--', alpha=0.8)
ax_gauge.text(trad, -0.15, f'Traditional\n{trad}', fontsize=9, color=RED,
              ha='center', fontfamily='monospace', fontweight='bold')

# MiroFish marker
ax_gauge.plot([score, score], [0.0, 1.0], color='white', linewidth=3.5, zorder=5)
ax_gauge.plot(score, 1.15, marker='v', color='white', markersize=14, zorder=5)
ax_gauge.text(score, -0.55, f'{score}', fontsize=32, fontweight='bold',
              color=TEXT, ha='center', fontfamily='monospace')
ax_gauge.text(score, -0.95, 'FEAR', fontsize=16, fontweight='bold',
              color=ORANGE, ha='center', fontfamily='monospace')

# Endpoint labels
ax_gauge.text(-2, 0.5, '0', fontsize=9, color=RED, ha='right',
              va='center', fontfamily='monospace')
ax_gauge.text(102, 0.5, '100', fontsize=9, color=GREEN, ha='left',
              va='center', fontfamily='monospace')

# ============================================================
# SENTIMENT DISTRIBUTION
# ============================================================
ax_dist = fig.add_axes([0.1, 0.60, 0.8, 0.16])
ax_dist.set_facecolor(BG)

categories = ['Extreme Fear', 'Fear', 'Neutral', 'Greed', 'Extreme Greed']
values = [3.2, 15.5, 60.8, 19.5, 0.9]
bar_colors = [RED, ORANGE, '#6e7681', '#2ea043', GREEN]

bars = ax_dist.barh(categories, values, color=bar_colors, height=0.55, alpha=0.9,
                     edgecolor=BG, linewidth=0.5)
ax_dist.set_xlim(0, 78)
ax_dist.invert_yaxis()
ax_dist.tick_params(colors=TEXT, labelsize=11)
for spine in ax_dist.spines.values():
    spine.set_visible(False)
ax_dist.tick_params(axis='x', colors=BG)  # hide x ticks
ax_dist.set_xticks([])

for bar, val in zip(bars, values):
    ax_dist.text(bar.get_width() + 1.2, bar.get_y() + bar.get_height()/2,
                 f'{val}%', va='center', fontsize=13, color=TEXT,
                 fontweight='bold', fontfamily='monospace')

ax_dist.set_title('Stage 1: Sentiment Analysis of 2,745 Real Posts',
                   fontsize=14, color=TEXT, fontfamily='monospace', pad=15,
                   fontweight='bold')

# Subtitle
ax_dist.text(0, -0.75, 'DeepSeek LLM with crypto-aware context  |  4-thread parallel scoring',
             fontsize=9, color=TEXT_DIM, fontfamily='monospace',
             transform=ax_dist.transAxes)

# ============================================================
# AGENT PANIC BREAKDOWN
# ============================================================
ax_agents = fig.add_axes([0.1, 0.33, 0.8, 0.20])
ax_agents.set_facecolor(BG)

agents = [
    ('Retail Panic Seller', 95),
    ('Newbie Investor', 92),
    ('Crypto KOL', 85),
    ('Leveraged Trader', 55),
    ('DeFi Degen', 50),
    ('Miner Operator', 35),
    ('Whale / Institution', 20),
    ('Diamond Hands', 15),
]

names = [a[0] for a in agents]
panics = [a[1] for a in agents]
agent_colors = [RED if p > 70 else ORANGE if p > 40 else GREEN for p in panics]

bars2 = ax_agents.barh(names, panics, color=agent_colors, height=0.6, alpha=0.9,
                        edgecolor=BG, linewidth=0.5)
ax_agents.set_xlim(0, 115)
ax_agents.invert_yaxis()
ax_agents.tick_params(colors=TEXT, labelsize=11)
for spine in ax_agents.spines.values():
    spine.set_visible(False)
ax_agents.set_xticks([])

for bar, val in zip(bars2, panics):
    label = f'{val}/100'
    ax_agents.text(bar.get_width() + 1.5, bar.get_y() + bar.get_height()/2,
                   label, va='center', fontsize=11, color=TEXT,
                   fontweight='bold', fontfamily='monospace')

ax_agents.set_title('Stage 2: 500 Agent Panic Simulation (OASIS Engine)',
                     fontsize=14, color=TEXT, fontfamily='monospace', pad=15,
                     fontweight='bold')

# Contagion label
ax_agents.text(1.0, -0.08, 'Contagion Effect: AMPLIFIED',
               fontsize=12, color=RED, fontfamily='monospace', fontweight='bold',
               transform=ax_agents.transAxes, ha='right')

# Draw contagion arrows
ax_agents.annotate('', xy=(92, 1.35), xytext=(85, 2.35),
                   arrowprops=dict(arrowstyle='->', color=RED, lw=1.8,
                                   connectionstyle='arc3,rad=-0.2'))
ax_agents.annotate('', xy=(85, 2.35), xytext=(55, 3.35),
                   arrowprops=dict(arrowstyle='->', color=ORANGE, lw=1.5,
                                   connectionstyle='arc3,rad=-0.15'))

# ============================================================
# DATA SOURCES
# ============================================================
ax_src = fig.add_axes([0.1, 0.18, 0.8, 0.10])
ax_src.set_facecolor(BG)
ax_src.axis('off')

ax_src.set_title('Data Sources', fontsize=14, color=TEXT,
                  fontfamily='monospace', pad=10, fontweight='bold')

sources = [
    ('Binance Square', 324, ORANGE, 'Playwright WAF bypass'),
    ('Twitter / X', 312, ACCENT, 'Nitter instances'),
    ('Reddit', 2111, GREEN, '14 subreddits RSS'),
]

total = sum(s[1] for s in sources)
left = 0.05
for name, count, color, method in sources:
    width = (count / total) * 0.9
    rect = FancyBboxPatch((left, 0.2), width, 0.5, boxstyle="round,pad=0.02",
                           facecolor=color, alpha=0.25, edgecolor=color, linewidth=1.5)
    ax_src.add_patch(rect)
    ax_src.text(left + width/2, 0.45, f'{name}\n{count:,}', fontsize=10,
                color=TEXT, ha='center', va='center', fontfamily='monospace',
                fontweight='bold')
    ax_src.text(left + width/2, 0.05, method, fontsize=7, color=TEXT_DIM,
                ha='center', va='center', fontfamily='monospace')
    left += width + 0.02

ax_src.set_xlim(0, 1)
ax_src.set_ylim(-0.1, 1.0)

# ============================================================
# VS COMPARISON
# ============================================================
ax_vs = fig.add_axes([0.1, 0.06, 0.8, 0.08])
ax_vs.set_facecolor(BG)
ax_vs.axis('off')
ax_vs.set_xlim(0, 10)
ax_vs.set_ylim(0, 2)

# Traditional box
rect1 = FancyBboxPatch((0.3, 0.3), 3.8, 1.4, boxstyle="round,pad=0.1",
                         facecolor=CARD_BG, edgecolor=RED, linewidth=2)
ax_vs.add_patch(rect1)
ax_vs.text(2.2, 1.35, 'Traditional Index', fontsize=10, color=TEXT_DIM,
           ha='center', fontfamily='monospace')
ax_vs.text(2.2, 0.65, '23  Extreme Fear', fontsize=14, color=RED,
           ha='center', fontweight='bold', fontfamily='monospace')

# VS
ax_vs.text(5.0, 1.0, 'VS', fontsize=16, color=TEXT_DIM, ha='center',
           va='center', fontweight='bold', fontfamily='monospace')

# MiroFish box
rect2 = FancyBboxPatch((5.9, 0.3), 3.8, 1.4, boxstyle="round,pad=0.1",
                         facecolor=CARD_BG, edgecolor=YELLOW, linewidth=2)
ax_vs.add_patch(rect2)
ax_vs.text(7.8, 1.35, 'MiroFish Edition', fontsize=10, color=ACCENT,
           ha='center', fontfamily='monospace')
ax_vs.text(7.8, 0.65, '40.1  Fear', fontsize=14, color=YELLOW,
           ha='center', fontweight='bold', fontfamily='monospace')

# ============================================================
# FOOTER
# ============================================================
fig.text(0.5, 0.025, 'github.com/robin-ph/btc-fear-greed-index',
         fontsize=11, color=ACCENT, ha='center', fontfamily='monospace')
fig.text(0.5, 0.008, '#Bitcoin  #MiroFish  #OASIS  #AI  #OpenSource',
         fontsize=9, color=TEXT_DIM, ha='center', fontfamily='monospace')

plt.savefig('/Users/penghan/Desktop/vibe_robin/btc_fear_index/infographic.png',
            dpi=200, bbox_inches='tight', facecolor=BG, pad_inches=0.4)
print('Saved: infographic.png')
