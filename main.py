"""BTC Fear & Greed Index - powered by MiroFish multi-agent simulation.

Usage:
    python main.py              # Full run (market data + scrapers + simulation)
    python main.py --market     # Market data only (no scraping)
    python main.py --dry-run    # Use mock social data for testing
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone

from market_data.coingecko import CoinGeckoClient
from mirofish.simulation import MiroFishSimulator
from index.fear_index import calculate_fear_index, format_report


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
            print(f"    Error: {e}")

    if "twitter" not in skip:
        try:
            from scrapers.twitter_scraper import scrape_twitter

            print("[*] Scraping Twitter/X...")
            posts = scrape_twitter()
            print(f"    Got {len(posts)} tweets")
            all_posts.extend(posts)
        except Exception as e:
            print(f"    Error: {e}")

    if "reddit" not in skip:
        try:
            from scrapers.reddit_scraper import scrape_reddit

            print("[*] Scraping Reddit...")
            posts = scrape_reddit()
            print(f"    Got {len(posts)} posts")
            all_posts.extend(posts)
        except Exception as e:
            print(f"    Error: {e}")

    return all_posts


def get_mock_social_data() -> list[dict]:
    """Mock social data for testing without scrapers."""
    return [
        {"source": "twitter", "text": "BTC is crashing! Selling everything before it goes to zero! #Bitcoin"},
        {"source": "twitter", "text": "Just bought the dip. BTC to 100k is inevitable. Diamond hands!"},
        {"source": "reddit", "text": "Is this the start of a bear market? My portfolio is down 40%"},
        {"source": "reddit", "text": "Whales are accumulating. This is a healthy correction."},
        {"source": "binance_square", "text": "BTC跌破支撑位了，恐慌性抛售开始了，大家快跑"},
        {"source": "binance_square", "text": "不要慌，每次大跌都是抄底机会，坚持持有"},
        {"source": "twitter", "text": "Liquidation cascade incoming. $500M in longs about to get rekt"},
        {"source": "reddit", "text": "I sold my house to buy BTC at 69k. Am I going to be okay?"},
        {"source": "twitter", "text": "Fear & greed at extreme fear. Historically best time to buy."},
        {"source": "binance_square", "text": "合约全部爆仓了，这个市场太疯狂了"},
    ]


def main():
    parser = argparse.ArgumentParser(description="BTC Fear & Greed Index (MiroFish)")
    parser.add_argument("--market", action="store_true", help="Market data only")
    parser.add_argument("--dry-run", action="store_true", help="Use mock social data")
    parser.add_argument("--output", "-o", type=str, help="Save result to JSON file")
    parser.add_argument(
        "--skip",
        nargs="*",
        choices=["binance", "twitter", "reddit"],
        default=[],
        help="Skip specific scrapers",
    )
    args = parser.parse_args()

    print("=" * 50)
    print("  BTC Fear & Greed Index (MiroFish Edition)")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 50)

    # 1. Get market data
    print("\n[*] Fetching market data from CoinGecko...")
    cg = CoinGeckoClient()
    try:
        market = cg.get_all_metrics()
        print(f"    BTC: ${market['raw']['price_usd']:,.0f}")
        print(f"    24h: {market['raw']['change_24h_pct']:.2f}%")
        print(f"    Dominance: {market['raw']['btc_dominance']:.1f}%")
    except Exception as e:
        print(f"    Error fetching market data: {e}")
        market = {"raw": {}, "scores": {"volatility": 50, "momentum": 50, "dominance": 50}}

    if args.market:
        # Market-only mode
        result = calculate_fear_index(market["scores"], 50.0)
        print(format_report(result))
        return

    # 2. Collect social data
    print()
    if args.dry_run:
        print("[*] Using mock social data (dry-run mode)")
        social_posts = get_mock_social_data()
    else:
        social_posts = collect_social_data(skip_scrapers=args.skip)

    if not social_posts:
        print("[!] No social data collected, using market data only")
        result = calculate_fear_index(market["scores"], 50.0)
        print(format_report(result))
        return

    print(f"\n[*] Total social posts collected: {len(social_posts)}")

    # 3. Run MiroFish multi-agent simulation
    print("\n[*] Running MiroFish multi-agent simulation...")
    simulator = MiroFishSimulator()
    sim_result = simulator.run_simulation(social_posts, market)
    sentiment_score = sim_result["sentiment_score"]
    print(f"    Sentiment score: {sentiment_score:.1f}/100")
    print(f"    Method: {sim_result['method']}")

    # 4. Calculate final index
    result = calculate_fear_index(market["scores"], sentiment_score)

    # 5. Display report
    print(format_report(result, sim_result))

    # 6. Optionally save to file
    if args.output:
        output = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "index": result,
            "simulation": {
                "score": sim_result["sentiment_score"],
                "method": sim_result["method"],
                "agents": sim_result.get("agent_responses", []),
                "posts_analyzed": sim_result.get("num_posts_analyzed", 0),
            },
            "market_raw": market.get("raw", {}),
        }
        with open(args.output, "w") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(f"\n[*] Results saved to {args.output}")


if __name__ == "__main__":
    main()
