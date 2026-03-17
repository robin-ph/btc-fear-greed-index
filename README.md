# BTC Fear & Greed Index — MiroFish Edition

A next-generation BTC Fear & Greed Index powered by **MiroFish/OASIS multi-agent simulation**. Instead of relying on outdated keyword-based sentiment analysis (VADER), this project uses 500 AI investor agents interacting on a simulated Reddit to model **panic contagion dynamics**.

## Why?

The traditional Crypto Fear & Greed Index (alternative.me) has fundamental flaws:

- **VADER sentiment analysis fails on crypto content** — scores "Daily Discussion Thread" as 96/100 Extreme Greed, rates sarcastic posts as genuine euphoria, and can't distinguish a newbie question from bullish sentiment
- **40% of the index relies on broken data sources** — surveys (suspended), Google Trends (can't distinguish fear from curiosity), and shallow social media scraping
- **Statistical aggregation ≠ understanding contagion** — knowing "30% of posts are fearful" doesn't tell you if that fear is spreading or being contained

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Data Collection                        │
│  Binance Square (Playwright) + Twitter (Nitter) + Reddit │
│                    ~2,800 posts                          │
├─────────────────────────────────────────────────────────┤
│               Stage 1: LLM Sentiment Analysis            │
│  DeepSeek batch-scores ALL posts with crypto-aware       │
│  context understanding + engagement weighting            │
│  Output: statistical sentiment distribution              │
├─────────────────────────────────────────────────────────┤
│            Stage 2: OASIS Multi-Agent Simulation         │
│  500 AI investor agents (diverse personas, randomized    │
│  entry prices, risk tolerance, personality)              │
│  Interact on simulated Reddit for 5 rounds               │
│  Output: panic contagion analysis                        │
├─────────────────────────────────────────────────────────┤
│                   Index Calculation                       │
│  Volatility(25%) + Momentum(25%) + Dominance(10%)        │
│  + MiroFish Sentiment(40%)                               │
│    = Stage1 × 0.4 + Stage2 × 0.6                        │
└─────────────────────────────────────────────────────────┘
```

## Agent Distribution (500 agents)

| Type | Count | Description |
|------|-------|-------------|
| High-fear retail | 120 | Bought near ATH, underwater, panic-prone |
| Moderate retail | 80 | Some experience, still emotional |
| Active traders | 60 | Technical analysis, day/swing trading |
| Leveraged traders | 40 | 5-50x leverage, liquidation-sensitive |
| Long-term holders | 50 | Since 2017, survived multiple -80% crashes |
| DeFi users | 35 | BTC as collateral, monitors liquidation thresholds |
| Institutional | 25 | Data-driven, contrarian |
| KOL/Influencers | 25 | Amplify sentiment for engagement |
| Miners | 20 | Concerned about hash rate and energy costs |
| Pure newbies | 45 | Entered last month, maximum panic on any red day |

Each agent has randomized: entry price, portfolio allocation, risk tolerance, MBTI personality, nationality, information sources.

## Quick Start

### Prerequisites

- Python 3.11 (for OASIS engine via conda)
- Python 3.12+ (for scrapers and analysis)
- Node.js (for `claude` CLI)
- [Claude Code](https://claude.ai/claude-code) with Max/Pro subscription (for scoring)

### Setup

```bash
# Clone
git clone https://github.com/robin-ph/btc-fear-greed-index.git
cd btc-fear-greed-index

# Create conda env for OASIS (requires Python 3.11)
conda create -n mirofish python=3.11 -y
conda run -n mirofish pip install camel-oasis==0.2.5 camel-ai==0.2.78

# Install main dependencies
pip install -r requirements.txt
pip install playwright && playwright install chromium

# Configure
cp .env.example .env
# Edit .env and add your DEEPSEEK_API_KEY
```

### Run

```bash
# Full pipeline (scrape + analyze + simulate + score)
python main.py -o result.json

# Market data only (no scraping)
python main.py --market

# Dry run with mock data
python main.py --dry-run

# Skip specific scrapers
python main.py --skip binance twitter
```

## Sample Output

```
╔══════════════════════════════════════════════════════════╗
║        BTC FEAR & GREED INDEX (MiroFish Edition)         ║
╠══════════════════════════════════════════════════════════╣
║  Score:  40.1 / 100    [      Fear      ]              ║
╠══════════════════════════════════════════════════════════╣
║  Components:                                             ║
║    Volatility                  6.2  (w=25%)         ║
║    Momentum                   51.5  (w=25%)         ║
║    Dominance                  56.0  (w=10%)         ║
║    Mirofish Sentiment         50.2  (w=40%)         ║
╠══════════════════════════════════════════════════════════╣
║  Posts analyzed:  2,745                                ║
║  Stage 1 (statistical):   50.2                          ║
║  Stage 2 (simulation):    50.2                          ║
║  OASIS: 49 posts, 0 comments, 3049 actions              ║
╚══════════════════════════════════════════════════════════╝
```

## Key Findings

**VADER vs DeepSeek sentiment analysis:**

| Post | VADER | DeepSeek | Actual |
|------|-------|----------|--------|
| "My Mom wants to buy Bitcoin" | 98 (Extreme Greed) | 50 (Neutral) | Neutral |
| "Daily Discussion Thread" | 96 (Extreme Greed) | 50 (Neutral) | Neutral |
| "Made profit $3!" (sarcasm) | 100 (Extreme Greed) | 45 (Neutral) | Sarcasm/Neutral |

**Panic contagion effect observed in OASIS simulation:**
- KOL agents amplify fear narratives → retail agents panic → newbies sell
- Even rational "Macro-Neutral" agents get infected under sustained social pressure
- Only Diamond Hands (2017 holders) and Whales maintain composure

## Data Sources

| Source | Method | Posts/run | Limitation |
|--------|--------|-----------|------------|
| Binance Square | Playwright (WAF bypass) | ~350 | No public API |
| Twitter/X | Nitter instances | ~300 | Unreliable, rate-limited |
| Reddit | RSS feeds (14 subreddits) | ~2,100 | No vote data via RSS |

**We need more data.** If exchanges (Binance, OKX, Bybit) opened public APIs for their community/square content, data volume could jump from 2,800 to 280,000+ posts per run.

## Cost

- DeepSeek sentiment analysis (2,800 posts): ~$0.05
- DeepSeek OASIS simulation (500 agents × 5 rounds): ~$0.70
- Claude scoring: free (via Claude Max OAuth)
- **Total per run: < $1**

## Contributing

PRs welcome! Especially:
- More data sources (Korean forums, Japanese 2ch, Telegram, Discord)
- Agent persona improvements (cultural differences in investor behavior)
- Historical backtesting (validate index against actual price movements)
- Better OASIS agent action rates (more posting/commenting vs liking)

## Credits

- [MiroFish](https://github.com/666ghj/MiroFish) — Open-source swarm intelligence engine
- [OASIS](https://github.com/camel-ai/oasis) — Social media simulation platform by CAMEL-AI
- [DeepSeek](https://deepseek.com) — LLM API for sentiment analysis and agent simulation
- [CoinGecko](https://coingecko.com) — Free market data API

## License

MIT
