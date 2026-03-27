"""Market data clients — CoinGecko, Binance Futures, on-chain."""

import requests


class RobustSession(requests.Session):
    """Session that retries without proxy on proxy/connection errors."""

    def request(self, *args, **kwargs):
        try:
            return super().request(*args, **kwargs)
        except (requests.exceptions.ProxyError, requests.exceptions.ConnectionError):
            kwargs["proxies"] = {"http": None, "https": None}
            return super().request(*args, **kwargs)
