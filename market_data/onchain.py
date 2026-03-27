"""On-chain data — transaction volume, mempool fees, network activity.

Uses blockchain.com and mempool.space free APIs (no auth needed).
"""

import numpy as np
from market_data import RobustSession


class OnchainClient:
    def __init__(self):
        self.session = RobustSession()

    def get_mempool_fees(self) -> dict:
        """Current recommended fees from mempool.space."""
        resp = self.session.get(
            "https://mempool.space/api/v1/fees/recommended",
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "fastest_fee": data["fastestFee"],
            "half_hour_fee": data["halfHourFee"],
            "hour_fee": data["hourFee"],
            "economy_fee": data["economyFee"],
        }

    def get_mempool_stats(self) -> dict:
        """Mempool transaction count and size."""
        resp = self.session.get(
            "https://mempool.space/api/mempool",
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "tx_count": data["count"],
            "vsize": data["vsize"],
            "total_fee": data["total_fee"],
        }

    def get_tx_volume_30d(self) -> list[float]:
        """30-day estimated transaction volume from blockchain.com."""
        resp = self.session.get(
            "https://api.blockchain.info/charts/estimated-transaction-volume",
            params={"timespan": "30days", "format": "json"},
            timeout=15,
        )
        resp.raise_for_status()
        values = resp.json().get("values", [])
        return [v["y"] for v in values]

    def get_all_metrics(self) -> dict:
        """Fetch all on-chain metrics and compute fear scores."""
        raw = {}
        scores = {}

        # Mempool fees
        try:
            fees = self.get_mempool_fees()
            raw["fastest_fee_sat"] = fees["fastest_fee"]
            raw["hour_fee_sat"] = fees["hour_fee"]
            scores["fees"] = self._score_fees(fees["fastest_fee"])
            print(f"    Mempool fee: {fees['fastest_fee']} sat/vB")
        except Exception as e:
            print(f"    Mempool fees error: {e}")
            scores["fees"] = 50

        # Mempool congestion
        try:
            mempool = self.get_mempool_stats()
            raw["mempool_tx_count"] = mempool["tx_count"]
            raw["mempool_vsize_mb"] = round(mempool["vsize"] / 1_000_000, 1)
            scores["congestion"] = self._score_congestion(mempool["tx_count"])
            print(f"    Mempool: {mempool['tx_count']} txs, "
                  f"{raw['mempool_vsize_mb']} MB")
        except Exception as e:
            print(f"    Mempool stats error: {e}")
            scores["congestion"] = 50

        # Transaction volume trend
        try:
            volumes = self.get_tx_volume_30d()
            if len(volumes) >= 7:
                recent_avg = np.mean(volumes[-7:])
                older_avg = np.mean(volumes[:-7])
                ratio = recent_avg / older_avg if older_avg > 0 else 1.0
                raw["tx_volume_7d_avg"] = round(recent_avg, 0)
                raw["tx_volume_trend"] = round(ratio, 3)
                scores["volume_trend"] = self._score_volume_trend(ratio)
        except Exception as e:
            print(f"    TX volume error: {e}")
            scores["volume_trend"] = 50

        # Combined score
        valid_scores = [v for v in scores.values() if v is not None]
        combined = np.mean(valid_scores) if valid_scores else 50
        scores["combined"] = round(float(combined), 2)

        return {"raw": raw, "scores": scores}

    def _score_fees(self, fastest_fee: int) -> float:
        """Fee level → 0-100. High fees during selloff = fear.
        But context matters: high fees can also mean bullish activity.
        We score: very low fees = low activity = slightly bearish.
        Normal fees = neutral. Very high = panic/congestion = fear.
        """
        # Typical range: 1-5 sat/vB (calm) to 50-200+ (panic/bull run)
        if fastest_fee <= 2:
            return 45  # Low activity, slightly bearish
        elif fastest_fee <= 10:
            return 55  # Normal, slightly bullish (healthy activity)
        elif fastest_fee <= 30:
            return 40  # Elevated, some urgency
        elif fastest_fee <= 100:
            return 25  # High congestion, likely panic
        else:
            return 10  # Extreme congestion

    def _score_congestion(self, tx_count: int) -> float:
        """Mempool tx count → 0-100. Very high = panic/urgency."""
        # Typical: 5K-20K normal, 50K+ congested, 100K+ extreme
        if tx_count < 5000:
            return 55  # Light mempool, calm
        elif tx_count < 20000:
            return 50  # Normal
        elif tx_count < 50000:
            return 35  # Elevated
        elif tx_count < 100000:
            return 20  # Congested
        else:
            return 10  # Extreme

    def _score_volume_trend(self, ratio: float) -> float:
        """7d/30d volume ratio → 0-100. Declining volume = fear."""
        # ratio < 0.7 = volume declining fast = fear
        # ratio ~1.0 = stable = neutral
        # ratio > 1.3 = volume surging = greed/FOMO
        if ratio < 0.5:
            return 15
        elif ratio < 0.8:
            return 30
        elif ratio < 1.0:
            return 45
        elif ratio < 1.2:
            return 55
        elif ratio < 1.5:
            return 70
        else:
            return 85
