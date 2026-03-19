# BTC Fear & Greed Index — MiroFish Edition

## Project Overview

A next-gen BTC Fear & Greed Index powered by **NVIDIA Nemotron 3 Super** (free via OpenRouter). Two-stage pipeline: **mega-batch sentiment scoring** + **10-agent multi-round real conversation simulation**. The core insight: knowing "30% of posts are fearful" doesn't tell you if fear is spreading — agent conversation contagion modeling does.

## Architecture

```
Data Collection → Stage 1 (Nemotron mega-batch) → Stage 2 (10-agent conversation) → Index
```

### Pipeline Flow

1. **Scrape** social data from 3 sources (~2,800 posts/run)
2. **Stage 1**: Nemotron mega-batch scores ALL posts (800/batch, 5 concurrent API calls)
3. **Stage 2**: 10 representative agents × 3 rounds of REAL conversation (each reads previous posts)
4. **Score**: Nemotron analyzes conversation for contagion dynamics
5. **Index**: Weighted blend → final 0-100 score
6. Total API calls: **~34** (3 Stage 1 + 30 Stage 2 + 1 scoring), all **free**

### Index Weights

| Component         | Weight | Source              |
|-------------------|--------|---------------------|
| Volatility        | 25%    | CoinGecko 30d data  |
| Momentum          | 25%    | CoinGecko price/vol |
| BTC Dominance     | 10%    | CoinGecko global    |
| MiroFish Sentiment| 40%    | Stage1×0.4 + Stage2×0.6 |

## Directory Structure

```
main.py                      # Entry point, CLI args, pipeline orchestration
daily_post.py                # Automated daily agent: pipeline → infographic → Twitter post
config/settings.py           # All config: API keys, weights, scraper params, subreddits/keywords
scrapers/
  binance_square.py          # Playwright + API interception, deep scroll, DOM fallback
  reddit_scraper.py          # RSS feeds (14 subreddits × 4 sorts + search), no API key needed
  twitter_scraper.py         # Nitter instances via Playwright, pagination
market_data/
  coingecko.py               # Free API: price, dominance, 30d volatility, momentum scoring
analysis/
  sentiment.py               # DeepSeek batch scoring (40 posts/batch, 4 threads), engagement weighting
mirofish/
  simulation.py              # Two-stage orchestrator: Stage1 → Stage2 → Claude scoring
  oasis_runner.py            # OASIS env setup, 500 agents, seed posts, run rounds, analyze DB
  profile_generator.py       # 10 agent types with randomized params (entry price, risk, MBTI, etc.)
index/
  fear_index.py              # Weighted index calculation + ASCII report formatter
generate_infographic.py      # Dynamic infographic generator (1080x1080, accepts result dict)
twitter_poster.py            # Twitter/X posting via twikit (cookie auth, no API key)
claude_proxy.py              # OpenAI-compatible HTTP proxy wrapping `claude` CLI (for OASIS)
output/                      # Generated infographics (gitignored)
results/                     # Archived daily results (gitignored)
```

## Key Technical Details

### Data Collection
- **Binance Square**: Playwright headless browser, intercepts `/bapi/` API responses + DOM scraping as fallback
- **Reddit**: Pure RSS (no API key), Atom XML parsing, 14 subreddits × 4 sort types + keyword search
- **Twitter**: Nitter proxy instances via Playwright, tries multiple instances until one works
- All scrapers deduplicate by first 80 chars of text

### Stage 1 — Nemotron Mega-Batch Sentiment (`analysis/sentiment.py`)
- **OpenRouter API** via OpenAI SDK (`openai.OpenAI` with custom base_url)
- Model: `nvidia/nemotron-3-super-120b-a12b:free` (optimized for multi-agent)
- Mega-batch: **800 posts per call**, 5 concurrent API threads
- Each post truncated to 200 chars, compact `idx|text` format
- Prompt returns `[[index, score], ...]` JSON array
- Engagement weighting: `log1p(likes/comments/retweets)` capped at 5
- Fallback: keyword-based scoring if API fails

### Stage 2 — Multi-Agent Conversation (`mirofish/simulation.py`)
- **10 representative agents** with distinct personas (not 500 identical weak agents)
- **3 rounds of REAL conversation**: each agent reads previous round's posts before responding
- Agent types: Retail Panic Seller, Pure Newbie, Leveraged Degen, Crypto KOL, TA, DeFi Degen, Moderate Retail, Miner, Institutional Whale, Diamond Hands OG
- 5 concurrent API calls per round, auto-retry on empty responses
- After conversation: Nemotron scores full transcript for contagion dynamics
- Returns: `{overall_score, contagion_effect, agents[{name, panic_level, reasoning}]}`
- Final: `stage1_score × 0.4 + stage2_score × 0.6`

### Legacy OASIS Path (optional, requires DeepSeek)
- `mirofish/oasis_runner.py` + `profile_generator.py` still exist
- Needs conda `mirofish` env (Python 3.11) + `DEEPSEEK_API_KEY`
- Not used by default pipeline

## Environment & Dependencies

- **Python 3.12+**: single environment, no conda needed
- **OpenRouter API**: all LLM tasks via NVIDIA Nemotron (free tier)
- **OpenAI SDK**: for OpenRouter API calls (OpenAI-compatible)
- **Playwright + Chromium**: Binance Square and Twitter scraping
- **No Reddit API key needed**: uses RSS feeds
- **Zero API cost** per run (free model)

### Key Env Vars
- `OPENROUTER_API_KEY` — required (free at openrouter.ai/keys)
- `OPENROUTER_MODEL` — defaults to `nvidia/nemotron-3-super-120b-a12b:free`
- `TWITTER_USERNAME` / `TWITTER_PASSWORD` — for auto-posting (twikit cookie auth)
- `TWITTER_TOTP_SECRET` — optional, for 2FA accounts

## CLI Usage

```bash
# Manual pipeline
python main.py -o result.json      # Full pipeline
python main.py --market             # Market data only
python main.py --dry-run            # Mock social data
python main.py --skip binance twitter  # Skip specific scrapers

# Daily auto-post agent
python daily_post.py                         # Full run + post to Twitter
python daily_post.py --dry-run               # Full run, save locally, no tweet
python daily_post.py --mock-data --dry-run   # Quick test with mock data
python daily_post.py --skip-pipeline --result result_v3.json --dry-run  # Test infographic + tweet from existing data
python daily_post.py --skip binance twitter  # Skip specific scrapers

# Infographic only
python generate_infographic.py result_v3.json  # Generate from existing result

# Cron (daily at 9:00 AM UTC)
# 0 9 * * * cd /path/to/btc_fear_index && python daily_post.py >> log/cron.log 2>&1
```

## Cost Per Run

- OpenRouter Nemotron (Stage 1 + Stage 2): **$0** (free model)
- ~34 API calls total per run
- **Total: $0**

## Known Limitations

- Twitter scraping via Nitter is unreliable (instances go down frequently)
- Reddit RSS provides no vote/comment count data
- Binance Square has WAF that may block scraping
- Free model occasionally returns empty responses (auto-retry handles this)
- 10 agents instead of 500, but with genuine multi-round conversation (better signal-to-noise)
