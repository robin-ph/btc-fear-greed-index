"""Generate Twitter article banner (1500x500 landscape)."""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

BG = '#0d1117'
TEXT = '#e6edf3'
TEXT_DIM = '#8b949e'
ACCENT = '#58a6ff'
RED = '#f85149'
ORANGE = '#d29922'
GREEN = '#3fb950'
YELLOW = '#e3b341'
BORDER = '#30363d'

fig, axes = plt.subplots(1, 3, figsize=(15, 5), facecolor=BG,
                          gridspec_kw={'width_ratios': [1.2, 1, 1]})

# ============================================================
# LEFT PANEL: Score
# ============================================================
ax = axes[0]
ax.set_facecolor(BG)
ax.axis('off')
ax.set_xlim(0, 10)
ax.set_ylim(0, 10)

ax.text(5, 8.8, 'BTC Fear & Greed Index', fontsize=18, fontweight='bold',
        color=TEXT, ha='center', fontfamily='monospace')
ax.text(5, 7.8, 'MiroFish Edition', fontsize=13, color=ACCENT,
        ha='center', fontfamily='monospace')

# Score number
ax.text(5, 5.0, '40.1', fontsize=60, fontweight='bold', color=ORANGE,
        ha='center', va='center', fontfamily='monospace')
ax.text(5, 2.8, 'FEAR', fontsize=20, fontweight='bold', color=ORANGE,
        ha='center', fontfamily='monospace')

# Gradient bar
gradient = np.linspace(0, 1, 256).reshape(1, -1)
colors_bar = ['#f85149', '#f85149', '#d29922', '#d29922', '#e6edf3', '#3fb950', '#3fb950']
cmap = matplotlib.colors.LinearSegmentedColormap.from_list('fg', colors_bar)
ax.imshow(gradient, aspect='auto', cmap=cmap, extent=[1, 9, 1.6, 2.2], alpha=0.8, zorder=1)
# Score marker on bar
score_x = 1 + (40.1 / 100) * 8
ax.plot([score_x, score_x], [1.4, 2.4], color='white', linewidth=3, zorder=5)
ax.plot(score_x, 2.5, marker='v', color='white', markersize=10, zorder=5)

# Traditional comparison
ax.text(5, 0.8, 'vs Traditional: 23 (Extreme Fear)', fontsize=10,
        color=RED, ha='center', fontfamily='monospace')

# ============================================================
# MIDDLE PANEL: Agent Panic Bars
# ============================================================
ax = axes[1]
ax.set_facecolor(BG)

agents = [
    ('Panic Seller', 95),
    ('Newbie', 92),
    ('KOL', 85),
    ('Trader', 55),
    ('DeFi', 50),
    ('Miner', 35),
    ('Whale', 20),
    ('HODLer', 15),
]

names = [a[0] for a in agents]
panics = [a[1] for a in agents]
colors = [RED if p > 70 else ORANGE if p > 40 else GREEN for p in panics]

bars = ax.barh(names, panics, color=colors, height=0.65, alpha=0.9)
ax.set_xlim(0, 118)
ax.invert_yaxis()
ax.tick_params(colors=TEXT, labelsize=9)
for spine in ax.spines.values():
    spine.set_visible(False)
ax.set_xticks([])

for bar, val in zip(bars, panics):
    ax.text(bar.get_width() + 2, bar.get_y() + bar.get_height()/2,
            str(val), va='center', fontsize=10, color=TEXT,
            fontweight='bold', fontfamily='monospace')

ax.set_title('500 Agents Panic Contagion', fontsize=12, color=TEXT,
             fontfamily='monospace', pad=10, fontweight='bold')
ax.text(0.5, -0.05, 'Contagion: AMPLIFIED', fontsize=10, color=RED,
        fontfamily='monospace', fontweight='bold',
        transform=ax.transAxes, ha='center')

# ============================================================
# RIGHT PANEL: Sentiment Distribution
# ============================================================
ax = axes[2]
ax.set_facecolor(BG)

cats = ['Ext Fear', 'Fear', 'Neutral', 'Greed', 'Ext Greed']
vals = [3.2, 15.5, 60.8, 19.5, 0.9]
bar_colors = [RED, ORANGE, '#6e7681', '#2ea043', GREEN]

bars2 = ax.barh(cats, vals, color=bar_colors, height=0.55, alpha=0.9)
ax.set_xlim(0, 80)
ax.invert_yaxis()
ax.tick_params(colors=TEXT, labelsize=9)
for spine in ax.spines.values():
    spine.set_visible(False)
ax.set_xticks([])

for bar, val in zip(bars2, vals):
    ax.text(bar.get_width() + 1.2, bar.get_y() + bar.get_height()/2,
            f'{val}%', va='center', fontsize=10, color=TEXT,
            fontweight='bold', fontfamily='monospace')

ax.set_title('2,745 Posts Analyzed', fontsize=12, color=TEXT,
             fontfamily='monospace', pad=10, fontweight='bold')
ax.text(0.5, -0.05, 'DeepSeek LLM Scoring', fontsize=10, color=ACCENT,
        fontfamily='monospace', transform=ax.transAxes, ha='center')

# ============================================================
# Bottom text
# ============================================================
fig.text(0.5, 0.01, 'github.com/robin-ph/btc-fear-greed-index   |   #Bitcoin  #MiroFish  #OASIS  #AI',
         fontsize=9, color=TEXT_DIM, ha='center', fontfamily='monospace')

plt.subplots_adjust(wspace=0.35, left=0.05, right=0.97, top=0.92, bottom=0.08)

plt.savefig('/Users/penghan/Desktop/vibe_robin/btc_fear_index/banner.png',
            dpi=200, bbox_inches='tight', facecolor=BG, pad_inches=0.3)
print('Saved: banner.png')
