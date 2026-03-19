"""Backtest weight optimization — 4-year BTC cycle.

Fetches historical data, computes daily component scores, and uses
scipy optimization to find weights that maximize contrarian predictive power.

A good fear index is CONTRARIAN:
  - Index says "Extreme Fear" → price tends to go UP (buy opportunity)
  - Index says "Extreme Greed" → price tends to go DOWN
  - Measured by negative correlation with future N-day returns.

Usage:
    python backtest.py                  # Full 4-year backtest
    python backtest.py --days 365       # 1-year backtest
    python backtest.py --forward 14     # Predict 14-day returns (default: 7)
"""

import argparse
import json
import time
from datetime import datetime, timezone, timedelta

import numpy as np
import requests
from scipy.optimize import minimize


# ═══════════════════════════════════════════════
#  Historical data fetchers
# ═══════════════════════════════════════════════

def fetch_prices(days: int) -> list[dict]:
    """Fetch BTC price history. Uses blockchain.com for >365d, CoinGecko for <=365d."""
    if days > 365:
        return _fetch_prices_blockchain(days)
    return _fetch_prices_coingecko(days)


def _fetch_prices_blockchain(days: int) -> list[dict]:
    """blockchain.com: supports up to 10+ years of daily BTC prices."""
    timespan = f"{days}days"
    print(f"[Data] Fetching {days}d BTC price from blockchain.com...")
    resp = requests.get(
        "https://api.blockchain.info/charts/market-price",
        params={"timespan": timespan, "format": "json", "rollingAverage": "1days"},
        timeout=30,
    )
    resp.raise_for_status()
    values = resp.json().get("values", [])

    # Also fetch volume
    print(f"[Data] Fetching {days}d BTC volume from blockchain.com...")
    try:
        vol_resp = requests.get(
            "https://api.blockchain.info/charts/trade-volume",
            params={"timespan": timespan, "format": "json", "rollingAverage": "1days"},
            timeout=30,
        )
        vol_resp.raise_for_status()
        vol_values = {v["x"]: v["y"] for v in vol_resp.json().get("values", [])}
    except Exception:
        vol_values = {}

    daily = []
    for v in values:
        ts = v["x"]
        date = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        daily.append({
            "date": date,
            "price": v["y"],
            "volume": vol_values.get(ts, 0),
        })

    print(f"       {len(daily)} days: {daily[0]['date']} → {daily[-1]['date']}")
    return daily


def _fetch_prices_coingecko(days: int) -> list[dict]:
    """CoinGecko: max 365 days for free tier."""
    print(f"[Data] Fetching {days}d BTC price from CoinGecko...")
    resp = requests.get(
        "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart",
        params={"vs_currency": "usd", "days": days, "interval": "daily"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    daily = []
    for i in range(len(data["prices"])):
        ts = data["prices"][i][0] / 1000
        daily.append({
            "date": datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d"),
            "price": data["prices"][i][1],
            "volume": data["total_volumes"][i][1] if i < len(data["total_volumes"]) else 0,
        })

    print(f"       {len(daily)} days: {daily[0]['date']} → {daily[-1]['date']}")
    return daily


def fetch_funding_rates(days: int) -> dict:
    """Binance Futures: historical funding rates (8-hourly → aggregated to daily)."""
    print(f"[Data] Fetching {days}d funding rate history from Binance...")
    all_data = []
    end_time = int(datetime.now(timezone.utc).timestamp() * 1000)
    start_time = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp() * 1000)

    while start_time < end_time:
        try:
            resp = requests.get(
                "https://fapi.binance.com/fapi/v1/fundingRate",
                params={"symbol": "BTCUSDT", "startTime": start_time, "limit": 1000},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            if not data:
                break
            all_data.extend(data)
            start_time = data[-1]["fundingTime"] + 1
            time.sleep(0.3)
        except Exception as e:
            print(f"       Funding fetch error: {e}")
            break

    # Aggregate to daily average
    daily = {}
    for d in all_data:
        date = datetime.fromtimestamp(
            d["fundingTime"] / 1000, tz=timezone.utc
        ).strftime("%Y-%m-%d")
        if date not in daily:
            daily[date] = []
        daily[date].append(float(d["fundingRate"]))

    result = {date: float(np.mean(rates)) for date, rates in daily.items()}
    dates = sorted(result.keys())
    print(f"       {len(result)} days: {dates[0] if dates else '?'} → {dates[-1] if dates else '?'}")
    return result


def fetch_long_short(days: int) -> dict:
    """Binance Futures: daily long/short ratio (paginated, max 500/req)."""
    print(f"[Data] Fetching long/short ratio history...")
    all_data = []
    remaining = min(days, 500)  # API max seems to be ~500 days
    end_time = int(datetime.now(timezone.utc).timestamp() * 1000)

    while remaining > 0:
        batch = min(remaining, 500)
        try:
            resp = requests.get(
                "https://fapi.binance.com/futures/data/globalLongShortAccountRatio",
                params={
                    "symbol": "BTCUSDT",
                    "period": "1d",
                    "limit": batch,
                    "endTime": end_time,
                },
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            if not data:
                break
            all_data.extend(data)
            end_time = data[0]["timestamp"] - 1
            remaining -= len(data)
            time.sleep(0.3)
        except Exception as e:
            print(f"       L/S fetch error: {e}")
            break

    result = {}
    for d in all_data:
        date = datetime.fromtimestamp(
            d["timestamp"] / 1000, tz=timezone.utc
        ).strftime("%Y-%m-%d")
        result[date] = float(d["longShortRatio"])

    dates = sorted(result.keys())
    print(f"       {len(result)} days: {dates[0] if dates else '?'} → {dates[-1] if dates else '?'}")
    return result


def fetch_alternative_fng(days: int) -> dict:
    """Alternative.me: traditional Fear & Greed Index as benchmark."""
    print(f"[Data] Fetching alternative.me F&G history...")
    result = {}

    # API returns max ~1000 per call, need multiple for 4 years
    limit = min(days, 1000)
    resp = requests.get(
        f"https://api.alternative.me/fng/?limit={limit}&format=json",
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json().get("data", [])

    for d in data:
        date = datetime.fromtimestamp(
            int(d["timestamp"]), tz=timezone.utc
        ).strftime("%Y-%m-%d")
        result[date] = int(d["value"])

    dates = sorted(result.keys())
    print(f"       {len(result)} days: {dates[0] if dates else '?'} → {dates[-1] if dates else '?'}")
    return result


# ═══════════════════════════════════════════════
#  Component score calculators
# ═══════════════════════════════════════════════

def score_volatility(prices: list[float], window: int = 14) -> float:
    """Annualized volatility → 0-100 (high vol = fear)."""
    if len(prices) < 2:
        return 50
    returns = np.diff(prices) / prices[:-1]
    recent = returns[-window:]
    vol = float(np.std(recent) * np.sqrt(365) * 100)

    if vol < 10: return 5
    elif vol < 30: return 5 + (vol - 10) * 1.25
    elif vol < 50: return 30 + (vol - 30) * 1.25
    elif vol < 80: return 55 + (vol - 50) * 1.0
    else: return min(100, 85 + (vol - 80) * 0.5)


def score_momentum(prices: list[float], window: int = 7) -> float:
    """Price change over window → 0-100 (negative = fear)."""
    if len(prices) < window + 1:
        return 50
    change = (prices[-1] - prices[-window - 1]) / prices[-window - 1] * 100
    # Map: -20% → 0, 0% → 50, +20% → 100
    return float(np.clip(50 + change * 2.5, 0, 100))


def score_volume_trend(volumes: list[float], window: int = 7) -> float:
    """Recent volume vs average → 0-100 (surge during decline = fear)."""
    if len(volumes) < window * 2:
        return 50
    recent = np.mean(volumes[-window:])
    older = np.mean(volumes[-window * 3:-window])
    if older == 0:
        return 50
    ratio = recent / older
    # High volume ratio = more activity = could be fear or greed
    # Combined with price direction elsewhere
    return float(np.clip(ratio * 50, 10, 90))


def score_funding(rate: float) -> float:
    """Funding rate → 0-100. Negative = shorts dominant = fear."""
    pct = rate * 100
    # Range: -0.1% to +0.1% typical
    return float(np.clip(50 + pct * 500, 0, 100))


def score_longshort(ratio: float) -> float:
    """Long/short ratio → 0-100. Low = fear, high = greed."""
    # 0.5 → ~10, 1.0 → 50, 2.0 → 90
    if ratio < 0.5: return 5
    elif ratio < 1.0: return 10 + (ratio - 0.5) * 80
    elif ratio < 2.0: return 50 + (ratio - 1.0) * 40
    else: return min(100, 90 + (ratio - 2.0) * 10)


def score_sma_distance(prices: list[float], sma_window: int = 200) -> float:
    """Price distance from 200-day SMA → 0-100.
    Below SMA = fear, above = greed."""
    if len(prices) < sma_window:
        return 50
    sma = np.mean(prices[-sma_window:])
    dist_pct = (prices[-1] - sma) / sma * 100
    # -30% below SMA → 10, at SMA → 50, +50% above → 90
    return float(np.clip(50 + dist_pct * 1.3, 5, 95))


def score_drawdown(prices: list[float], window: int = 90) -> float:
    """Drawdown from recent high → 0-100. Deep drawdown = extreme fear."""
    if len(prices) < window:
        return 50
    recent_high = max(prices[-window:])
    dd_pct = (prices[-1] - recent_high) / recent_high * 100  # negative
    # 0% dd → 70 (near high = greed), -20% → 30 (fear), -50% → 5
    return float(np.clip(70 + dd_pct * 1.3, 5, 95))


# ═══════════════════════════════════════════════
#  Build daily dataset
# ═══════════════════════════════════════════════

COMPONENTS = [
    "volatility", "momentum", "volume_trend",
    "funding", "longshort",
    "sma_distance", "drawdown",
]


def build_dataset(
    prices_data: list[dict],
    funding_hist: dict,
    ls_hist: dict,
    forward_days: int = 7,
) -> list[dict]:
    """Build daily rows with all component scores + future returns."""
    all_prices = [d["price"] for d in prices_data]
    all_volumes = [d["volume"] for d in prices_data]
    dates = [d["date"] for d in prices_data]

    rows = []
    lookback = 200  # Need 200 days for SMA

    for i in range(lookback, len(all_prices) - forward_days):
        date = dates[i]
        price_history = all_prices[:i + 1]
        vol_history = all_volumes[:i + 1]

        future_price = all_prices[i + forward_days]
        future_return = (future_price - all_prices[i]) / all_prices[i] * 100

        scores = {
            "volatility": score_volatility(price_history),
            "momentum": score_momentum(price_history),
            "volume_trend": score_volume_trend(vol_history),
            "sma_distance": score_sma_distance(price_history),
            "drawdown": score_drawdown(price_history),
        }

        if date in funding_hist:
            scores["funding"] = score_funding(funding_hist[date])
        if date in ls_hist:
            scores["longshort"] = score_longshort(ls_hist[date])

        rows.append({
            "date": date,
            "price": all_prices[i],
            "future_return": future_return,
            "scores": scores,
        })

    return rows


# ═══════════════════════════════════════════════
#  Evaluation & optimization
# ═══════════════════════════════════════════════

def compute_index(scores: dict, weights: dict) -> float:
    """Weighted average of available components."""
    total = 0
    total_w = 0
    for comp, w in weights.items():
        if comp in scores and w > 0:
            total += scores[comp] * w
            total_w += w
    return total / total_w if total_w > 0 else 50


def evaluate(rows: list[dict], weights: dict) -> dict:
    """Evaluate weights: correlation, directional accuracy, Sharpe-like."""
    indices = []
    returns = []

    for row in rows:
        idx = compute_index(row["scores"], weights)
        indices.append(idx)
        returns.append(row["future_return"])

    idx_arr = np.array(indices)
    ret_arr = np.array(returns)

    # 1. Correlation (want negative)
    corr = float(np.corrcoef(idx_arr, ret_arr)[0, 1])
    if np.isnan(corr):
        corr = 0

    # 2. Directional accuracy
    fear_mask = idx_arr < 25
    greed_mask = idx_arr > 75
    fear_days = int(np.sum(fear_mask))
    greed_days = int(np.sum(greed_mask))

    fear_acc = float(np.mean(ret_arr[fear_mask] > 0)) if fear_days > 0 else 0.5
    greed_acc = float(np.mean(ret_arr[greed_mask] < 0)) if greed_days > 0 else 0.5

    # 3. Average return in fear vs greed zones
    fear_avg_ret = float(np.mean(ret_arr[fear_mask])) if fear_days > 0 else 0
    greed_avg_ret = float(np.mean(ret_arr[greed_mask])) if greed_days > 0 else 0

    # 4. Combined score (higher is better)
    # Negative correlation + high accuracy + big spread between fear/greed returns
    spread = fear_avg_ret - greed_avg_ret  # want positive (fear → up, greed → down)
    n_signals = fear_days + greed_days
    signal_ratio = n_signals / len(rows) if rows else 0

    combined = (
        -corr * 0.3
        + (fear_acc * 0.5 + greed_acc * 0.5) * 0.3
        + np.clip(spread / 20, -1, 1) * 0.3
        + signal_ratio * 0.1  # Bonus for actually producing signals
    )

    return {
        "correlation": round(corr, 4),
        "fear_accuracy": round(fear_acc, 4),
        "greed_accuracy": round(greed_acc, 4),
        "fear_days": fear_days,
        "greed_days": greed_days,
        "fear_avg_return": round(fear_avg_ret, 2),
        "greed_avg_return": round(greed_avg_ret, 2),
        "signal_ratio": round(signal_ratio, 4),
        "score": round(float(combined), 4),
    }


def optimize_weights(rows: list[dict]) -> dict:
    """Use scipy to find optimal weights via Nelder-Mead optimization."""
    # Find which components have enough data
    comp_coverage = {c: 0 for c in COMPONENTS}
    for row in rows:
        for c in row["scores"]:
            comp_coverage[c] = comp_coverage.get(c, 0) + 1

    # Only use components with >50% coverage
    threshold = len(rows) * 0.5
    active_comps = [c for c in COMPONENTS if comp_coverage.get(c, 0) > threshold]
    print(f"\n[Optimize] Active components ({len(active_comps)}):")
    for c in active_comps:
        print(f"           {c}: {comp_coverage[c]}/{len(rows)} days ({comp_coverage[c]/len(rows)*100:.0f}%)")

    def objective(x):
        weights = {comp: max(0, xi) for comp, xi in zip(active_comps, x)}
        result = evaluate(rows, weights)
        return -result["score"]  # Minimize negative score

    # Multiple random starts to avoid local minima
    best_result = None
    best_weights = None
    best_score = -999

    rng = np.random.RandomState(42)
    for trial in range(50):
        x0 = rng.dirichlet(np.ones(len(active_comps)))  # Random simplex point
        try:
            res = minimize(
                objective, x0,
                method="Nelder-Mead",
                options={"maxiter": 2000, "xatol": 0.001, "fatol": 0.0001},
            )
            weights = {comp: max(0, xi) for comp, xi in zip(active_comps, res.x)}
            total = sum(weights.values())
            weights = {k: v / total for k, v in weights.items()}  # Normalize
            ev = evaluate(rows, weights)

            if ev["score"] > best_score:
                best_score = ev["score"]
                best_weights = weights
                best_result = ev
        except Exception:
            continue

    return {"weights": best_weights, "evaluation": best_result}


def grid_search_coarse(rows: list[dict]) -> list[dict]:
    """Coarse grid search for interpretability + validation."""
    from itertools import product

    comp_coverage = {c: 0 for c in COMPONENTS}
    for row in rows:
        for c in row["scores"]:
            comp_coverage[c] = comp_coverage.get(c, 0) + 1

    threshold = len(rows) * 0.5
    active = [c for c in COMPONENTS if comp_coverage.get(c, 0) > threshold]

    steps = [0, 10, 20, 30, 40]
    results = []

    for combo in product(steps, repeat=len(active)):
        if sum(combo) == 0 or sum(combo) > 100:
            continue
        weights = dict(zip(active, [c / 100 for c in combo]))
        ev = evaluate(rows, weights)
        if ev["fear_days"] + ev["greed_days"] >= 5:  # At least some signals
            results.append({"weights": weights, **ev})

    results.sort(key=lambda r: r["score"], reverse=True)
    return results


def main():
    parser = argparse.ArgumentParser(description="Backtest weight optimization (4y)")
    parser.add_argument("--days", type=int, default=1460, help="Backtest period (default: 1460 = 4 years)")
    parser.add_argument("--forward", type=int, default=7, help="Forward return days (default: 7)")
    args = parser.parse_args()

    print("=" * 65)
    print("  BTC Fear & Greed Index — 4-Year Cycle Backtest")
    print(f"  Period: {args.days} days | Forward: {args.forward}d returns")
    print("=" * 65)

    # ── Fetch all data ──
    prices = fetch_prices(args.days)
    time.sleep(1.5)
    funding = fetch_funding_rates(args.days)
    time.sleep(1.5)
    longshort = fetch_long_short(args.days)
    time.sleep(1.5)
    alt_fng = fetch_alternative_fng(min(args.days, 1000))

    # ── Build dataset ──
    print(f"\n[Build] Computing daily component scores...")
    rows = build_dataset(prices, funding, longshort, args.forward)
    print(f"        {len(rows)} tradeable days with forward returns")

    if len(rows) < 30:
        print("[!] Not enough data")
        return

    # ── Optimize ──
    print("\n[Optimize] Running scipy optimization (50 random starts)...")
    opt = optimize_weights(rows)

    print("\n[Optimize] Running coarse grid search for validation...")
    grid = grid_search_coarse(rows)

    # ── Results ──
    print("\n" + "=" * 65)
    print("  SCIPY OPTIMAL WEIGHTS")
    print("=" * 65)

    opt_w = opt["weights"]
    opt_e = opt["evaluation"]
    for comp in sorted(opt_w, key=opt_w.get, reverse=True):
        pct = opt_w[comp] * 100
        if pct > 1:
            print(f"    {comp:<20s} {pct:>5.1f}%")

    print(f"\n    Correlation (7d):   {opt_e['correlation']:>7.3f} (want negative)")
    print(f"    Fear accuracy:     {opt_e['fear_accuracy']:>7.1%} ({opt_e['fear_days']} days)")
    print(f"    Greed accuracy:    {opt_e['greed_accuracy']:>7.1%} ({opt_e['greed_days']} days)")
    print(f"    Avg return (fear): {opt_e['fear_avg_return']:>+6.1f}%")
    print(f"    Avg return (greed):{opt_e['greed_avg_return']:>+6.1f}%")
    print(f"    Combined score:    {opt_e['score']:>7.3f}")

    print(f"\n{'=' * 65}")
    print("  TOP 5 GRID SEARCH RESULTS")
    print("=" * 65)

    for i, r in enumerate(grid[:5]):
        w_parts = [f"{k}={v * 100:.0f}%" for k, v in r["weights"].items() if v > 0]
        print(f"  #{i+1}  score={r['score']:.3f}  corr={r['correlation']:.3f}  "
              f"fear_acc={r['fear_accuracy']:.0%}  greed_acc={r['greed_accuracy']:.0%}")
        print(f"       {' | '.join(w_parts)}")

    # ── Benchmark: Alternative.me ──
    print(f"\n{'=' * 65}")
    print("  BENCHMARK: Alternative.me Traditional F&G Index")
    print("=" * 65)

    alt_idx = []
    alt_ret = []
    for row in rows:
        if row["date"] in alt_fng:
            alt_idx.append(alt_fng[row["date"]])
            alt_ret.append(row["future_return"])

    if len(alt_idx) > 30:
        alt_idx_arr = np.array(alt_idx)
        alt_ret_arr = np.array(alt_ret)
        alt_corr = float(np.corrcoef(alt_idx_arr, alt_ret_arr)[0, 1])

        alt_fear = alt_idx_arr < 25
        alt_greed = alt_idx_arr > 75
        alt_fear_acc = float(np.mean(alt_ret_arr[alt_fear] > 0)) if np.sum(alt_fear) > 0 else 0
        alt_greed_acc = float(np.mean(alt_ret_arr[alt_greed] < 0)) if np.sum(alt_greed) > 0 else 0
        alt_fear_ret = float(np.mean(alt_ret_arr[alt_fear])) if np.sum(alt_fear) > 0 else 0
        alt_greed_ret = float(np.mean(alt_ret_arr[alt_greed])) if np.sum(alt_greed) > 0 else 0

        print(f"    Correlation (7d):   {alt_corr:>7.3f}")
        print(f"    Fear accuracy:     {alt_fear_acc:>7.1%} ({int(np.sum(alt_fear))} days)")
        print(f"    Greed accuracy:    {alt_greed_acc:>7.1%} ({int(np.sum(alt_greed))} days)")
        print(f"    Avg return (fear): {alt_fear_ret:>+6.1f}%")
        print(f"    Avg return (greed):{alt_greed_ret:>+6.1f}%")
        print(f"    Data points:       {len(alt_idx)}")
    else:
        print("    Not enough overlapping data")

    # ── Save ──
    output = {
        "config": {"days": args.days, "forward_days": args.forward},
        "data_points": len(rows),
        "date_range": f"{rows[0]['date']} → {rows[-1]['date']}",
        "optimal_weights": {k: round(v, 4) for k, v in opt_w.items()},
        "optimal_evaluation": opt_e,
        "grid_top5": grid[:5],
    }
    with open("backtest_results.json", "w") as f:
        json.dump(output, f, indent=2, default=str)

    # ── Print config snippet ──
    print(f"\n{'=' * 65}")
    print("  RECOMMENDED config/settings.py WEIGHTS")
    print(f"{'=' * 65}")

    # Map backtest names → config names
    NAME_MAP = {
        "volatility": "volatility",
        "momentum": "momentum",
        "volume_trend": "momentum",  # Merge into momentum
        "funding": "derivatives",
        "longshort": "derivatives",
        "sma_distance": "momentum",  # Merge
        "drawdown": "volatility",    # Merge
    }

    config_w = {}
    for comp, w in opt_w.items():
        config_key = NAME_MAP.get(comp, comp)
        config_w[config_key] = config_w.get(config_key, 0) + w

    # Reserve % for non-backtestable components
    backtested_total = sum(config_w.values())
    sentiment_reserve = 0.25  # Social media + agent sim
    onchain_reserve = 0.05
    trends_reserve = 0.05
    scale = 1 - sentiment_reserve - onchain_reserve - trends_reserve

    print(f"\nWEIGHTS = {{")
    for k in ["volatility", "momentum", "derivatives"]:
        v = config_w.get(k, 0) * scale
        print(f'    "{k}": {v:.2f},')
    print(f'    "dominance": 0.05,')
    print(f'    "onchain": {onchain_reserve:.2f},')
    print(f'    "mirofish_sentiment": {sentiment_reserve:.2f},')
    print(f'    "google_trends": {trends_reserve:.2f},')
    print(f"}}")

    print(f"\n[*] Results saved to backtest_results.json")


if __name__ == "__main__":
    main()
