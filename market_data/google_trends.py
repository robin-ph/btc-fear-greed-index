"""Google Trends BTC search interest — fear/greed proxy.

Spikes in "bitcoin crash" = fear. Spikes in "buy bitcoin" = greed.
Uses pytrends (unofficial API, rate-limited but works for daily runs).
"""

import time

try:
    from pytrends.request import TrendReq
    HAS_PYTRENDS = True
except ImportError:
    HAS_PYTRENDS = False


FEAR_KEYWORDS = ["bitcoin crash", "crypto crash", "bitcoin sell"]
GREED_KEYWORDS = ["buy bitcoin", "bitcoin price", "bitcoin ATH"]


class GoogleTrendsClient:
    def __init__(self):
        if not HAS_PYTRENDS:
            raise ImportError(
                "pytrends not installed. Run: pip install pytrends"
            )
        self.pytrends = TrendReq(hl="en-US", tz=0, timeout=(10, 30))

    def get_fear_greed_trend(self) -> dict:
        """Compare fear vs greed search volume over last 7 days."""
        try:
            # Fear keywords
            fear_score = self._get_keyword_interest(FEAR_KEYWORDS)
            time.sleep(2)  # Rate limit

            # Greed keywords
            greed_score = self._get_keyword_interest(GREED_KEYWORDS)

            # Relative ratio
            total = fear_score + greed_score
            if total == 0:
                ratio = 0.5
            else:
                ratio = greed_score / total  # 0 = all fear, 1 = all greed

            return {
                "raw": {
                    "fear_interest": fear_score,
                    "greed_interest": greed_score,
                    "greed_ratio": round(ratio, 3),
                },
                "scores": {
                    "combined": round(ratio * 100, 2),
                },
            }

        except Exception as e:
            print(f"    Google Trends error: {e}")
            return {
                "raw": {},
                "scores": {"combined": 50},
            }

    def _get_keyword_interest(self, keywords: list[str]) -> float:
        """Get average interest for a group of keywords over 7 days."""
        try:
            self.pytrends.build_payload(
                keywords[:5],  # pytrends max 5 keywords
                timeframe="now 7-d",
                geo="",
            )
            data = self.pytrends.interest_over_time()
            if data.empty:
                return 0

            # Average of most recent values across all keywords
            recent = data.iloc[-7:]  # Last 7 data points
            keyword_cols = [c for c in data.columns if c != "isPartial"]
            return float(recent[keyword_cols].mean().mean())

        except Exception:
            return 0

    def get_all_metrics(self) -> dict:
        return self.get_fear_greed_trend()
