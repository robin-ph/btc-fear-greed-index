"""CoinGecko free API - BTC market data."""

import requests
import numpy as np
from config.settings import COINGECKO_BASE_URL


class CoinGeckoClient:
    def __init__(self):
        self.base_url = COINGECKO_BASE_URL
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    def get_btc_price_data(self) -> dict:
        """Get BTC price, 24h change, 24h volume."""
        resp = self.session.get(
            f"{self.base_url}/simple/price",
            params={
                "ids": "bitcoin",
                "vs_currencies": "usd",
                "include_24hr_change": "true",
                "include_24hr_vol": "true",
            },
        )
        resp.raise_for_status()
        data = resp.json()["bitcoin"]
        return {
            "price_usd": data["usd"],
            "change_24h_pct": data["usd_24h_change"],
            "volume_24h_usd": data["usd_24h_vol"],
        }

    def get_btc_dominance(self) -> float:
        """Get BTC market cap dominance percentage."""
        resp = self.session.get(f"{self.base_url}/global")
        resp.raise_for_status()
        return resp.json()["data"]["market_cap_percentage"]["btc"]

    def get_30d_prices(self) -> list[float]:
        """Get 30-day daily closing prices for volatility calculation."""
        resp = self.session.get(
            f"{self.base_url}/coins/bitcoin/market_chart",
            params={"vs_currency": "usd", "days": 30},
        )
        resp.raise_for_status()
        return [p[1] for p in resp.json()["prices"]]

    def calc_volatility(self, prices: list[float]) -> float:
        """Calculate annualized volatility from daily prices.

        Returns a 0-100 score where higher = more volatile = more fear.
        """
        if len(prices) < 2:
            return 50.0
        prices_arr = np.array(prices)
        daily_returns = np.diff(prices_arr) / prices_arr[:-1]
        volatility = np.std(daily_returns) * np.sqrt(365) * 100  # annualized %

        # Map volatility to 0-100 fear score
        # BTC typical range: 30-80% annualized
        # <30% = very calm (score ~10), 50% = moderate (score ~50), >80% = extreme (score ~90)
        if volatility < 10:
            score = 5
        elif volatility < 30:
            score = 5 + (volatility - 10) * (25 / 20)   # 5-30
        elif volatility < 50:
            score = 30 + (volatility - 30) * (25 / 20)  # 30-55
        elif volatility < 80:
            score = 55 + (volatility - 50) * (30 / 30)  # 55-85
        else:
            score = min(100, 85 + (volatility - 80) * 0.5)  # 85-100
        return round(score, 2)

    def calc_momentum_score(self, price_data: dict, prices_30d: list[float]) -> float:
        """Calculate momentum score.

        Compares current volume and price to 30-day averages.
        Negative momentum + high volume = fear.
        """
        current_price = price_data["price_usd"]
        change_24h = price_data["change_24h_pct"]
        avg_price_30d = np.mean(prices_30d)

        # Price below 30d average = bearish
        price_ratio = current_price / avg_price_30d

        # Combine: negative change + below average = high fear
        if change_24h < -5 and price_ratio < 0.95:
            return max(0, 10 + change_24h * 2)  # extreme fear
        elif change_24h < 0:
            return max(0, 50 + change_24h * 5)
        elif change_24h > 5:
            return min(100, 70 + change_24h * 2)  # greed
        else:
            return min(100, 50 + change_24h * 5)

    def calc_dominance_score(self, dominance: float) -> float:
        """Calculate fear score from BTC dominance.

        Higher BTC dominance = flight to safety = more fear.
        Lower dominance = altcoin season = greed.
        """
        # BTC dominance typically ranges 40-70%
        # >60% = fear (flight to BTC), <45% = greed (altcoin season)
        score = min(100, max(0, (dominance - 40) * (100 / 30)))
        return round(score, 2)

    def get_all_metrics(self) -> dict:
        """Fetch all metrics and return fear scores."""
        price_data = self.get_btc_price_data()
        dominance = self.get_btc_dominance()
        prices_30d = self.get_30d_prices()

        return {
            "raw": {
                **price_data,
                "btc_dominance": dominance,
            },
            "scores": {
                "volatility": self.calc_volatility(prices_30d),
                "momentum": self.calc_momentum_score(price_data, prices_30d),
                "dominance": self.calc_dominance_score(dominance),
            },
        }
