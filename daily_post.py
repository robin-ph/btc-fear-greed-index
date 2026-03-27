"""Automated daily BTC Fear & Greed Index agent.

Runs the full pipeline, generates an infographic, and posts to Twitter/X.

Usage:
    python daily_post.py                    # Full run + post to Twitter
    python daily_post.py --dry-run          # Full run, no tweet (save locally)
    python daily_post.py --skip-pipeline    # Reuse latest result, just generate + post
    python daily_post.py --result result_v3.json  # Use specific result file
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone

from market_data.coingecko import CoinGeckoClient
from market_data.derivatives import DerivativesClient
from market_data.onchain import OnchainClient
from mirofish.simulation import MiroFishSimulator
from index.fear_index import calculate_fear_index
from generate_infographic import generate_infographic
from edge_poster import post_tweet as edge_post_tweet


def collect_social_data(skip_scrapers: list[str] = None) -> list[dict]:
    """Collect social media posts from all sources."""
    skip = skip_scrapers or []
    all_posts = []

    if "binance" not in skip:
        try:
            from scrapers.binance_square import scrape_binance_square
            print("[*] Scraping Binance Square...")
            posts = scrape_binance_square()
            print(f"    Got {len(posts)} posts")
            all_posts.extend(posts)
        except Exception as e:
            print(f"    Binance Square error: {e}")

    if "twitter" not in skip:
        try:
            from scrapers.twitter_scraper import scrape_twitter
            print("[*] Scraping Twitter/X...")
            posts = scrape_twitter()
            print(f"    Got {len(posts)} tweets")
            all_posts.extend(posts)
        except Exception as e:
            print(f"    Twitter error: {e}")

    if "reddit" not in skip:
        try:
            from scrapers.reddit_scraper import scrape_reddit
            print("[*] Scraping Reddit...")
            posts = scrape_reddit()
            print(f"    Got {len(posts)} posts")
            all_posts.extend(posts)
        except Exception as e:
            print(f"    Reddit error: {e}")

    return all_posts


def run_pipeline(skip_scrapers: list[str] = None, dry_run_data: bool = False) -> dict:
    """Run the full BTC Fear & Greed pipeline. Returns result dict."""
    now = datetime.now(timezone.utc)
    print("=" * 50)
    print("  BTC Fear & Greed Index — Daily Agent")
    print(f"  {now.strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 50)

    # 1. Market data (CoinGecko)
    print("\n[*] Fetching market data from CoinGecko...")
    cg = CoinGeckoClient()
    try:
        market = cg.get_all_metrics()
        raw = market["raw"]
        print(f"    BTC: ${raw['price_usd']:,.0f}")
        print(f"    24h: {raw['change_24h_pct']:.2f}%")
        print(f"    Dominance: {raw['btc_dominance']:.1f}%")
    except Exception as e:
        print(f"    Market data error: {e}")
        market = {
            "raw": {},
            "scores": {"volatility": 50, "momentum": 50, "dominance": 50},
        }

    # 1b. Derivatives data (Binance Futures)
    print("\n[*] Fetching derivatives data from Binance Futures...")
    try:
        deriv = DerivativesClient().get_all_metrics()
        market["scores"]["derivatives"] = deriv["scores"]["combined"]
        market["raw"].update({f"deriv_{k}": v for k, v in deriv["raw"].items()})
        dr = deriv["raw"]
        print(f"    Funding rate: {dr.get('funding_rate', 0):.6f}")
        print(f"    Long/short ratio: {dr.get('long_short_ratio', 0):.3f}")
    except Exception as e:
        print(f"    Derivatives error: {e}")
        market["scores"]["derivatives"] = 50

    # 1c. On-chain data (mempool.space + blockchain.com)
    print("\n[*] Fetching on-chain data...")
    try:
        onchain = OnchainClient().get_all_metrics()
        market["scores"]["onchain"] = onchain["scores"]["combined"]
        market["raw"].update({f"onchain_{k}": v for k, v in onchain["raw"].items()})
    except Exception as e:
        print(f"    On-chain error: {e}")
        market["scores"]["onchain"] = 50

    # 1d. Google Trends (optional — pytrends may not be installed)
    print("\n[*] Fetching Google Trends...")
    try:
        from market_data.google_trends import GoogleTrendsClient
        gtrends = GoogleTrendsClient().get_all_metrics()
        market["scores"]["google_trends"] = gtrends["scores"]["combined"]
        market["raw"].update({f"gtrends_{k}": v for k, v in gtrends["raw"].items()})
        gr = gtrends["raw"]
        print(f"    Fear interest: {gr.get('fear_interest', 0):.0f}")
        print(f"    Greed interest: {gr.get('greed_interest', 0):.0f}")
    except ImportError:
        print("    pytrends not installed, skipping (pip install pytrends)")
        market["scores"]["google_trends"] = 50
    except Exception as e:
        print(f"    Google Trends error: {e}")
        market["scores"]["google_trends"] = 50

    # 2. Social data
    if dry_run_data:
        print("\n[*] Using mock social data (dry-run)")
        social_posts = _mock_social_data()
    else:
        print()
        social_posts = collect_social_data(skip_scrapers=skip_scrapers)

    if not social_posts:
        print("[!] No social data, using market data only")
        index_result = calculate_fear_index(market["scores"], 50.0)
        return _bundle_result(index_result, None, market, now)

    print(f"\n[*] Total posts collected: {len(social_posts)}")

    # 3. MiroFish simulation
    print("\n[*] Running MiroFish multi-agent simulation...")
    simulator = MiroFishSimulator()
    sim_result = simulator.run_simulation(social_posts, market)
    sentiment_score = sim_result["sentiment_score"]
    print(f"    Sentiment score: {sentiment_score:.1f}/100")

    # 4. Calculate index
    index_result = calculate_fear_index(market["scores"], sentiment_score)

    return _bundle_result(index_result, sim_result, market, now)


def _bundle_result(
    index_result: dict,
    sim_result: dict | None,
    market: dict,
    now: datetime,
) -> dict:
    """Bundle all results into the standard output format."""
    result = {
        "timestamp": now.isoformat(),
        "index": index_result,
        "simulation": {
            "score": sim_result["sentiment_score"] if sim_result else 50.0,
            "method": sim_result.get("method", "none") if sim_result else "market_only",
            "agents": sim_result.get("agent_responses", []) if sim_result else [],
            "posts_analyzed": sim_result.get("num_posts_analyzed", 0) if sim_result else 0,
        },
        "market_raw": market.get("raw", {}),
    }
    return result


def compose_tweet(result: dict) -> str:
    """Compose tweet text from result data."""
    index = result["index"]
    score = index["value"]
    label = index["label"]

    market = result.get("market_raw", {})
    price = market.get("price_usd", 0)
    change = market.get("change_24h_pct", 0)

    sim = result.get("simulation", {})
    posts = sim.get("posts_analyzed", 0)
    agents = sim.get("agents", [])

    change_sign = "+" if change >= 0 else ""
    date_str = datetime.now().strftime("%b %d")

    lines = [
        f"BTC Fear & Greed Index — {date_str}",
        "",
        f"{score:.0f}/100 [{label}]",
        f"BTC ${price:,.0f} ({change_sign}{change:.1f}%)",
    ]

    if posts:
        lines.append("")
        lines.append(
            f"500 AI investors analyzed {posts:,} posts across 3 platforms."
        )

    # Top panic agent one-liner
    if agents:
        top = max(agents, key=lambda a: a.get("panic_level", 0))
        lines.append(f"Highest panic: {top['name']} ({top['panic_level']}/100)")

    lines.append("")
    lines.append("github.com/robin-ph/btc-fear-greed-index")

    return "\n".join(lines)


def save_result(result: dict, output_dir: str = "results") -> str:
    """Save result JSON with date stamp."""
    os.makedirs(output_dir, exist_ok=True)
    try:
        dt = datetime.fromisoformat(result["timestamp"])
    except (ValueError, KeyError):
        dt = datetime.now(timezone.utc)
    filename = os.path.join(output_dir, f"{dt.strftime('%Y-%m-%d')}.json")
    with open(filename, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"[*] Result saved: {filename}")
    return filename


async def post_to_twitter(image_path: str, tweet_text: str):
    """Post infographic + text to Twitter/X via Edge browser."""
    await edge_post_tweet(image_path, tweet_text)
    print(f"[*] Tweet posted successfully via Edge!")


def _mock_social_data() -> list[dict]:
    return [
        {"source": "twitter", "text": "BTC is crashing! Selling everything! #Bitcoin"},
        {"source": "twitter", "text": "Just bought the dip. BTC to 100k!"},
        {"source": "reddit", "text": "Is this the start of a bear market? Portfolio down 40%"},
        {"source": "reddit", "text": "Whales are accumulating. Healthy correction."},
        {"source": "binance_square", "text": "BTC跌破支撑位了，恐慌性抛售开始了"},
        {"source": "binance_square", "text": "不要慌，每次大跌都是抄底机会"},
        {"source": "twitter", "text": "Liquidation cascade incoming. $500M longs about to get rekt"},
        {"source": "reddit", "text": "I sold my house to buy BTC at 69k. Am I going to be okay?"},
        {"source": "twitter", "text": "Fear & greed at extreme fear. Best time to buy historically."},
        {"source": "binance_square", "text": "合约全部爆仓了，这个市场太疯狂了"},
    ]


def main():
    parser = argparse.ArgumentParser(description="Daily BTC Fear & Greed Agent")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Run full pipeline but don't post to Twitter",
    )
    parser.add_argument(
        "--mock-data", action="store_true",
        help="Use mock social data instead of scraping",
    )
    parser.add_argument(
        "--skip-pipeline", action="store_true",
        help="Skip pipeline, reuse existing result file",
    )
    parser.add_argument(
        "--result", type=str,
        help="Path to existing result JSON (implies --skip-pipeline)",
    )
    parser.add_argument(
        "--skip", nargs="*",
        choices=["binance", "twitter", "reddit"],
        default=[],
        help="Skip specific scrapers",
    )
    parser.add_argument(
        "--no-image", action="store_true",
        help="Post text only, skip infographic generation",
    )
    args = parser.parse_args()

    # ── Step 1: Get result data ──
    if args.result:
        print(f"[*] Loading result from {args.result}")
        with open(args.result) as f:
            result = json.load(f)
    elif args.skip_pipeline:
        # Find latest result
        for candidate in ["results/", "."]:
            if not os.path.isdir(candidate):
                continue
            files = sorted(
                [f for f in os.listdir(candidate) if f.endswith(".json") and "result" in f.lower()],
                reverse=True,
            )
            if files:
                path = os.path.join(candidate, files[0])
                print(f"[*] Loading latest result: {path}")
                with open(path) as f:
                    result = json.load(f)
                break
        else:
            print("[!] No result file found. Run without --skip-pipeline first.")
            sys.exit(1)
    else:
        result = run_pipeline(
            skip_scrapers=args.skip,
            dry_run_data=args.mock_data,
        )
        save_result(result)

    # ── Step 2: Generate infographic ──
    image_path = None
    if not args.no_image:
        try:
            image_path = generate_infographic(result)
        except Exception as e:
            print(f"[!] Infographic generation failed: {e}")
            print("[!] Will post text-only tweet")

    # ── Step 3: Compose tweet ──
    tweet_text = compose_tweet(result)

    print("\n" + "=" * 50)
    print("  Tweet Preview")
    print("=" * 50)
    print(tweet_text)
    if image_path:
        print(f"\n  Image: {image_path}")
    print("=" * 50)

    # ── Step 4: Post to Twitter ──
    # Safety check: don't post if market data is missing (BTC $0)
    market_price = result.get("market_raw", {}).get("price_usd", 0)
    if market_price == 0 and not args.dry_run:
        print("\n[!] BTC price is $0 — market data missing. Refusing to post.")
        print("[!] Result and infographic saved locally. Fix and retry.")
        sys.exit(1)

    if args.dry_run:
        print("\n[DRY RUN] Tweet not posted. Image and result saved locally.")
        # Print the final index report
        score = result["index"]["value"]
        label = result["index"]["label"]
        print(f"\n  Final Score: {score:.1f}/100 [{label}]")
    else:
        print("\n[*] Posting to Twitter/X...")
        try:
            asyncio.run(post_to_twitter(image_path, tweet_text))
        except Exception as e:
            print(f"[!] Twitter posting failed: {e}")
            print("[!] Result and infographic saved locally.")
            sys.exit(1)

    print("\n[*] Daily agent run complete.")


if __name__ == "__main__":
    main()
