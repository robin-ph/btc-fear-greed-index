import os
from dotenv import load_dotenv

load_dotenv()

# === OpenRouter API (all LLM tasks) ===
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3-super-120b-a12b:free")

# === Reddit ===
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", "btc_fear_index/1.0")

# === Twitter ===
TWITTER_USERNAME = os.getenv("TWITTER_USERNAME", "")
TWITTER_PASSWORD = os.getenv("TWITTER_PASSWORD", "")

# === CoinGecko (free, no key needed) ===
COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"

# === Index weights (4-year cycle backtest optimized) ===
WEIGHTS = {
    "volatility": 0.47,        # Volatility + drawdown (strongest predictor in backtest)
    "momentum": 0.14,          # Price momentum + volume trend
    "derivatives": 0.04,       # Funding rate + long/short ratio
    "dominance": 0.05,         # BTC market cap dominance
    "onchain": 0.05,           # Mempool fees + tx volume
    "mirofish_sentiment": 0.20,  # Social media + agent simulation
    "google_trends": 0.05,     # Search interest fear/greed
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

# === Twitter Posting (twikit) ===
TWITTER_COOKIES_FILE = "twitter_cookies.json"
TWITTER_TOTP_SECRET = os.getenv("TWITTER_TOTP_SECRET", "")

# === Output paths ===
OUTPUT_DIR = "output"
RESULTS_DIR = "results"
