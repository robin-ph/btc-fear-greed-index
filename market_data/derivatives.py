"""Binance Futures derivatives data — funding rate, long/short ratio, open interest.

All endpoints are public, no auth needed.
"""

import numpy as np
from market_data import RobustSession


BINANCE_FUTURES_BASE = "https://fapi.binance.com"


class DerivativesClient:
    def __init__(self):
        self.session = RobustSession()
        self.session.headers.update({"Accept": "application/json"})

    def get_funding_rate(self) -> float:
        """Current BTC funding rate. Positive = longs pay shorts (bullish crowd)."""
        resp = self.session.get(
            f"{BINANCE_FUTURES_BASE}/fapi/v1/fundingRate",
            params={"symbol": "BTCUSDT", "limit": 1},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return float(data[0]["fundingRate"])

    def get_long_short_ratio(self) -> dict:
        """Global long/short account ratio."""
        resp = self.session.get(
            f"{BINANCE_FUTURES_BASE}/futures/data/globalLongShortAccountRatio",
            params={"symbol": "BTCUSDT", "period": "1h", "limit": 1},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()[0]
        return {
            "long_pct": float(data["longAccount"]),
            "short_pct": float(data["shortAccount"]),
            "ratio": float(data["longShortRatio"]),
        }

    def get_top_trader_ratio(self) -> dict:
        """Top trader long/short ratio (professional sentiment)."""
        resp = self.session.get(
            f"{BINANCE_FUTURES_BASE}/futures/data/topLongShortAccountRatio",
            params={"symbol": "BTCUSDT", "period": "1h", "limit": 1},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()[0]
        return {
            "long_pct": float(data["longAccount"]),
            "short_pct": float(data["shortAccount"]),
            "ratio": float(data["longShortRatio"]),
        }

    def get_open_interest(self) -> float:
        """Open interest in BTC."""
        resp = self.session.get(
            f"{BINANCE_FUTURES_BASE}/fapi/v1/openInterest",
            params={"symbol": "BTCUSDT"},
            timeout=10,
        )
        resp.raise_for_status()
        return float(resp.json()["openInterest"])

    def get_all_metrics(self) -> dict:
        """Fetch all derivatives metrics and compute fear scores."""
        raw = {}
        scores = {}

        try:
            funding = self.get_funding_rate()
            raw["funding_rate"] = funding
            scores["funding"] = self._score_funding(funding)
        except Exception as e:
            print(f"    Funding rate error: {e}")
            scores["funding"] = 50

        try:
            ls = self.get_long_short_ratio()
            raw["long_short_ratio"] = ls["ratio"]
            raw["long_pct"] = ls["long_pct"]
            raw["short_pct"] = ls["short_pct"]
            scores["long_short"] = self._score_long_short(ls["ratio"])
        except Exception as e:
            print(f"    Long/short ratio error: {e}")
            scores["long_short"] = 50

        try:
            top = self.get_top_trader_ratio()
            raw["top_trader_ratio"] = top["ratio"]
            scores["top_trader"] = self._score_long_short(top["ratio"])
        except Exception as e:
            print(f"    Top trader ratio error: {e}")
            scores["top_trader"] = 50

        try:
            oi = self.get_open_interest()
            raw["open_interest_btc"] = oi
        except Exception as e:
            print(f"    Open interest error: {e}")

        # Combined derivatives fear score (0=extreme fear, 100=extreme greed)
        combined = np.mean([scores["funding"], scores["long_short"], scores["top_trader"]])
        # Invert: high greed in derivatives = high fear score (contrarian)
        # Actually keep as-is: high long/short = greed, low = fear
        scores["combined"] = round(float(combined), 2)

        return {"raw": raw, "scores": scores}

    def _score_funding(self, rate: float) -> float:
        """Funding rate → 0-100 score. Negative = fear, positive = greed."""
        # Typical range: -0.01% to +0.05%
        # Very negative (<-0.005) = extreme fear (10)
        # Zero = neutral (50)
        # Very positive (>0.03) = extreme greed (90)
        pct = rate * 100  # Convert to percentage
        if pct < -0.5:
            return 5
        elif pct < 0:
            return 25 + pct * 50  # -0.5→25, 0→50 (actually: -0.5→0, 0→25)
        else:
            return min(100, 50 + pct * 100)  # 0→50, 0.05→55, 0.5→100

    def _score_long_short(self, ratio: float) -> float:
        """Long/short ratio → 0-100. <0.8 = extreme fear, >2.0 = extreme greed."""
        # ratio 0.5 → 10 (extreme fear)
        # ratio 1.0 → 50 (neutral)
        # ratio 2.0 → 90 (extreme greed)
        if ratio < 0.5:
            return 5
        elif ratio < 1.0:
            return 10 + (ratio - 0.5) * 80  # 0.5→10, 1.0→50
        elif ratio < 2.0:
            return 50 + (ratio - 1.0) * 40  # 1.0→50, 2.0→90
        else:
            return min(100, 90 + (ratio - 2.0) * 10)
