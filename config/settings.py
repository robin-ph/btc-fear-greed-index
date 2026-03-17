import os
from dotenv import load_dotenv

load_dotenv()

# === Claude (uses `claude` CLI with OAuth, no API key needed) ===

# === Reddit ===
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", "btc_fear_index/1.0")

# === Twitter ===
TWITTER_USERNAME = os.getenv("TWITTER_USERNAME", "")
TWITTER_PASSWORD = os.getenv("TWITTER_PASSWORD", "")

# === MiroFish ===
MIROFISH_BASE_URL = os.getenv("MIROFISH_BASE_URL", "http://localhost:5001")

# === CoinGecko (free, no key needed) ===
COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"

# === Index weights ===
WEIGHTS = {
    "volatility": 0.25,
    "momentum": 0.25,
    "dominance": 0.10,
    "mirofish_sentiment": 0.40,
}

# === Scraper settings ===
BINANCE_SQUARE_MAX_POSTS = 5000
TWITTER_MAX_TWEETS = 5000
REDDIT_MAX_POSTS = 5000

REDDIT_SUBREDDITS = [
    "Bitcoin", "CryptoCurrency", "BitcoinMarkets", "CryptoMarkets",
    "btc", "SatoshiStreetBets", "CryptoMoonShots", "ethtrader",
    "BitcoinBeginners", "CryptoCurrencies", "altcoin",
    "BitcoinMining", "defi", "CryptoTechnology",
]

TWITTER_KEYWORDS = [
    "#BTC", "$BTC", "Bitcoin crash", "Bitcoin dump", "Bitcoin moon",
    "Bitcoin bear", "Bitcoin bull", "BTC liquidation", "crypto fear",
    "crypto panic", "Bitcoin sell", "Bitcoin buy the dip",
    "BTC price", "Bitcoin whale", "crypto market crash",
    "Bitcoin bottom", "BTC ATH", "Bitcoin recession",
    "crypto bloodbath", "Bitcoin recovery",
]

BINANCE_SQUARE_HASHTAGS = [
    "BTC", "Bitcoin", "CryptoMarket", "BTCAnalysis",
    "CryptoCrash", "BTCPrice", "Cryptocurrency",
]
