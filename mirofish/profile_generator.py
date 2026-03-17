"""Generate 500 diverse BTC investor agent profiles for OASIS simulation.

Each agent has randomized parameters: entry price, portfolio size,
risk tolerance, experience, nationality, personality type.
Same investor "type" will have different reactions based on these parameters.
"""

import json
import random
from dataclasses import dataclass

# Reproducible randomness
random.seed(42)

# === Agent type distributions (matching real market) ===
AGENT_TYPES = {
    "retail_high_fear": {
        "count": 120,  # 24% - largest group, most emotional
        "base_persona": (
            "A retail crypto investor who {entry_context}. "
            "{risk_desc} Checks portfolio {check_freq}. "
            "{social_influence} {emotional_state}"
        ),
        "risk_range": (0.1, 0.3),
        "entry_prices": (60000, 73000),  # Bought near highs
        "portfolio_pct": (0.3, 0.9),  # Large % of savings in crypto
    },
    "retail_moderate": {
        "count": 80,  # 16%
        "base_persona": (
            "A retail investor who {entry_context}. "
            "Has some experience with market volatility. "
            "{risk_desc} {emotional_state}"
        ),
        "risk_range": (0.3, 0.5),
        "entry_prices": (30000, 55000),
        "portfolio_pct": (0.1, 0.4),
    },
    "active_trader": {
        "count": 60,  # 12%
        "base_persona": (
            "An active crypto trader who {entry_context}. "
            "Focuses on technical analysis, chart patterns, and momentum. "
            "{risk_desc} Trades {trade_freq}. {emotional_state}"
        ),
        "risk_range": (0.4, 0.6),
        "entry_prices": (20000, 65000),
        "portfolio_pct": (0.15, 0.5),
    },
    "leveraged_trader": {
        "count": 40,  # 8%
        "base_persona": (
            "A leveraged crypto trader using {leverage}x on futures. "
            "{entry_context}. Extremely sensitive to price swings. "
            "A {liquidation_pct}% drop means liquidation. "
            "{risk_desc} {emotional_state}"
        ),
        "risk_range": (0.2, 0.4),
        "entry_prices": (50000, 72000),
        "portfolio_pct": (0.2, 0.8),
        "leverage_range": (5, 50),
    },
    "defi_user": {
        "count": 35,  # 7%
        "base_persona": (
            "A DeFi user who {entry_context}. "
            "Uses BTC as collateral in lending protocols with "
            "liquidation threshold at ${liquidation_price:,.0f}. "
            "{risk_desc} {emotional_state}"
        ),
        "risk_range": (0.3, 0.5),
        "entry_prices": (25000, 60000),
        "portfolio_pct": (0.2, 0.6),
    },
    "long_term_holder": {
        "count": 50,  # 10%
        "base_persona": (
            "A long-term BTC holder who {entry_context}. "
            "Has survived {num_crashes} major crashes. "
            "Believes in BTC fundamentals and {hold_reason}. "
            "{risk_desc} {emotional_state}"
        ),
        "risk_range": (0.6, 0.9),
        "entry_prices": (3000, 30000),
        "portfolio_pct": (0.05, 0.3),
    },
    "institutional": {
        "count": 25,  # 5%
        "base_persona": (
            "An institutional investor managing a {fund_type}. "
            "{entry_context}. Makes decisions based on {analysis_type}. "
            "{risk_desc} {emotional_state}"
        ),
        "risk_range": (0.5, 0.8),
        "entry_prices": (10000, 50000),
        "portfolio_pct": (0.02, 0.1),
    },
    "kol_influencer": {
        "count": 25,  # 5%
        "base_persona": (
            "A crypto influencer with {followers} followers on {platform}. "
            "{entry_context}. {influence_style} "
            "Sentiment reflects and amplifies crowd mood. {emotional_state}"
        ),
        "risk_range": (0.3, 0.6),
        "entry_prices": (15000, 50000),
        "portfolio_pct": (0.1, 0.4),
    },
    "miner": {
        "count": 20,  # 4%
        "base_persona": (
            "A BTC miner operating {mining_scale} in {mining_location}. "
            "Break-even cost is ~${breakeven:,.0f}. "
            "{entry_context}. {risk_desc} {emotional_state}"
        ),
        "risk_range": (0.4, 0.7),
        "entry_prices": (10000, 40000),
        "portfolio_pct": (0.1, 0.3),
    },
    "pure_newbie": {
        "count": 45,  # 9%
        "base_persona": (
            "A complete crypto newbie who {entry_context}. "
            "Has no understanding of market cycles, technical analysis, or fundamentals. "
            "Heard about BTC from {heard_from}. "
            "{risk_desc} {emotional_state}"
        ),
        "risk_range": (0.05, 0.2),
        "entry_prices": (65000, 74000),
        "portfolio_pct": (0.1, 0.5),
    },
}

# Randomization pools
FIRST_NAMES = [
    "James", "Emma", "Liam", "Olivia", "Noah", "Ava", "Ethan", "Sophia",
    "Mason", "Isabella", "Lucas", "Mia", "Oliver", "Charlotte", "Aiden",
    "Amelia", "Elijah", "Harper", "Logan", "Evelyn", "Alex", "Luna",
    "Jack", "Chloe", "Ryan", "Zoe", "Tyler", "Lily", "Dylan", "Grace",
    "Wei", "Yuki", "Raj", "Priya", "Ahmed", "Fatima", "Carlos", "Maria",
    "Jin", "Hana", "Kai", "Mei", "Sato", "Kim", "Park", "Chen",
    "Ivan", "Olga", "Hans", "Ingrid", "Pierre", "Sophie", "Marco", "Giulia",
    "Takeshi", "Sakura", "Hiroshi", "Yuna", "Dmitri", "Natasha",
]

COUNTRIES = [
    "US", "US", "US", "US",  # US overrepresented
    "UK", "Germany", "France", "Canada", "Australia",
    "Japan", "South Korea", "China", "India", "Singapore",
    "UAE", "Brazil", "Nigeria", "Turkey", "Indonesia",
    "Thailand", "Vietnam", "Philippines", "Mexico", "Argentina",
]

MBTIS = [
    "INTJ", "INTP", "ENTJ", "ENTP",
    "INFJ", "INFP", "ENFJ", "ENFP",
    "ISTJ", "ISFJ", "ESTJ", "ESFJ",
    "ISTP", "ISFP", "ESTP", "ESFP",
]

CHECK_FREQS = [
    "every 5 minutes", "every 15 minutes", "every hour",
    "several times a day", "once a day", "a few times a week",
]

TRADE_FREQS = [
    "multiple times daily", "daily", "several times a week", "weekly",
]

SOCIAL_INFLUENCES = [
    "Heavily influenced by crypto Twitter FUD and hype.",
    "Gets most information from Reddit crypto communities.",
    "Follows several crypto YouTubers and takes their advice seriously.",
    "Primarily reads Binance Square for market opinions.",
    "Relies on Telegram groups for trading signals.",
    "Mostly influenced by friends and family who also invest.",
]

HOLD_REASONS = [
    "sees it as digital gold and a hedge against inflation",
    "believes in the decentralization movement",
    "sees it as the future of money",
    "views it purely as an asymmetric bet",
    "thinks central banks will eventually debase all fiat currencies",
]

FUND_TYPES = [
    "crypto hedge fund", "family office crypto allocation",
    "venture fund with crypto exposure", "crypto-focused ETF",
    "multi-strategy fund with digital asset sleeve",
]

ANALYSIS_TYPES = [
    "on-chain data and whale tracking",
    "macro economic indicators and correlation analysis",
    "quantitative models and risk metrics",
    "fundamental analysis and network effects",
]

INFLUENCE_STYLES = [
    "Creates sensational content that amplifies market emotions.",
    "Posts balanced analysis but frames it dramatically for engagement.",
    "Flip-flops between extreme bull and bear narratives for clicks.",
    "Primarily shares bearish content during downtrends for engagement.",
    "Creates educational content but sentiment matches the crowd.",
]

HEARD_FROM = [
    "friends at a party", "a TikTok video", "a coworker",
    "a news headline", "a YouTube ad", "family members",
    "a podcast", "social media trending topics",
]

MINING_SCALES = [
    "a small home mining rig", "a mid-size facility with 100 ASICs",
    "a large industrial operation with 500+ ASICs",
    "a small mining pool", "a containerized mining farm",
]

MINING_LOCATIONS = [
    "Texas", "Wyoming", "Kazakhstan", "Iceland", "Paraguay",
    "Georgia (country)", "British Columbia", "Oman", "Ethiopia",
]

PLATFORMS = ["Twitter/X", "YouTube", "Reddit", "TikTok", "Binance Square"]


def _random_entry_context(entry_price: float, current_price: float = 74500) -> str:
    pnl_pct = (current_price - entry_price) / entry_price * 100
    if pnl_pct > 50:
        return f"bought BTC at ${entry_price:,.0f} and is up {pnl_pct:.0f}%"
    elif pnl_pct > 10:
        return f"bought BTC at ${entry_price:,.0f} and is up {pnl_pct:.0f}% but worried about giving back gains"
    elif pnl_pct > -10:
        return f"bought BTC at ${entry_price:,.0f} and is roughly break-even"
    elif pnl_pct > -30:
        return f"bought BTC at ${entry_price:,.0f} and is down {abs(pnl_pct):.0f}%, feeling anxious"
    else:
        return f"bought BTC at ${entry_price:,.0f} and is deep underwater, down {abs(pnl_pct):.0f}%"


def _random_risk_desc(risk_tolerance: float) -> str:
    if risk_tolerance < 0.2:
        return "Extremely risk-averse, prone to panic selling at any sign of trouble."
    elif risk_tolerance < 0.4:
        return "Low risk tolerance, gets nervous during volatility."
    elif risk_tolerance < 0.6:
        return "Moderate risk tolerance, can handle some drawdowns."
    elif risk_tolerance < 0.8:
        return "High risk tolerance, comfortable with significant volatility."
    else:
        return "Very high risk tolerance, views crashes as buying opportunities."


def _random_emotional_state(risk_tolerance: float, pnl_pct: float) -> str:
    if pnl_pct < -20 and risk_tolerance < 0.3:
        states = [
            "Currently in a state of panic and considering selling everything.",
            "Losing sleep over portfolio losses and checking price obsessively.",
            "Seriously questioning whether crypto was a mistake.",
            "Feeling sick watching the portfolio bleed every day.",
        ]
    elif pnl_pct < -10:
        states = [
            "Feeling anxious but trying to hold on.",
            "Worried about further downside but hesitant to sell at a loss.",
            "Stress levels elevated, seeking reassurance from online communities.",
        ]
    elif pnl_pct > 20:
        states = [
            "Feeling confident but worried about a potential reversal.",
            "Enjoying unrealized gains but nervous about when to take profit.",
            "Optimistic about the future but watching for warning signs.",
        ]
    else:
        states = [
            "Cautiously observing the market.",
            "Neutral but attentive to any major moves.",
            "Waiting for clearer signals before making any decisions.",
        ]
    return random.choice(states)


def generate_profiles(n: int = 500) -> list[dict]:
    """Generate n diverse agent profiles."""
    profiles = []
    agent_id = 0

    for type_name, config in AGENT_TYPES.items():
        # Scale count proportionally if n != 500
        count = round(config["count"] * n / 500)

        for i in range(count):
            if agent_id >= n:
                break

            # Randomize parameters
            entry_price = random.uniform(*config["entry_prices"])
            risk_tolerance = random.uniform(*config["risk_range"])
            portfolio_pct = random.uniform(*config["portfolio_pct"])
            pnl_pct = (74500 - entry_price) / entry_price * 100

            # Build persona with randomized context
            kwargs = {
                "entry_context": _random_entry_context(entry_price),
                "risk_desc": _random_risk_desc(risk_tolerance),
                "emotional_state": _random_emotional_state(risk_tolerance, pnl_pct),
                "check_freq": random.choice(CHECK_FREQS),
                "social_influence": random.choice(SOCIAL_INFLUENCES),
                "trade_freq": random.choice(TRADE_FREQS),
                "num_crashes": random.randint(1, 5),
                "hold_reason": random.choice(HOLD_REASONS),
                "fund_type": random.choice(FUND_TYPES),
                "analysis_type": random.choice(ANALYSIS_TYPES),
                "followers": f"{random.randint(10, 2000)}K",
                "platform": random.choice(PLATFORMS),
                "influence_style": random.choice(INFLUENCE_STYLES),
                "heard_from": random.choice(HEARD_FROM),
                "mining_scale": random.choice(MINING_SCALES),
                "mining_location": random.choice(MINING_LOCATIONS),
                "breakeven": random.uniform(25000, 55000),
                "leverage": random.randint(
                    *config.get("leverage_range", (5, 20))
                ),
                "liquidation_pct": round(100 / random.randint(5, 50), 1),
                "liquidation_price": entry_price * random.uniform(0.5, 0.8),
            }

            try:
                persona = config["base_persona"].format(**kwargs)
            except (KeyError, ValueError):
                persona = f"A {type_name.replace('_', ' ')} crypto investor. {kwargs['entry_context']}. {kwargs['risk_desc']}"

            name = random.choice(FIRST_NAMES)
            country = random.choice(COUNTRIES)
            age = random.randint(18, 65)
            gender = random.choice(["male", "female"])
            mbti = random.choice(MBTIS)

            # Generate username
            suffixes = [str(random.randint(1, 9999)), "_btc", "_crypto", f"_{age}", ""]
            username = f"{name.lower()}{random.choice(suffixes)}"

            # Bio based on type
            bio_templates = {
                "retail_high_fear": "Crypto investor. Just trying not to lose money.",
                "retail_moderate": "BTC holder. Learning the ropes.",
                "active_trader": f"Crypto trader. Charts are life. Trading {random.choice(TRADE_FREQS)}.",
                "leveraged_trader": f"{kwargs['leverage']}x leverage degen. NFA.",
                "defi_user": "DeFi enthusiast. Yield farming and lending.",
                "long_term_holder": f"HODLing since {random.randint(2015, 2021)}. Diamond hands.",
                "institutional": f"Managing {random.choice(FUND_TYPES)}.",
                "kol_influencer": f"{kwargs['followers']} followers. Crypto content creator.",
                "miner": f"Mining BTC in {kwargs['mining_location']}.",
                "pure_newbie": "New to crypto. What's a blockchain??",
            }

            profiles.append({
                "user_id": agent_id,
                "username": username,
                "name": name,
                "bio": bio_templates.get(type_name, "Crypto enthusiast."),
                "persona": persona,
                "karma": random.randint(10, 50000),
                "age": age,
                "gender": gender,
                "mbti": mbti,
                "country": country,
                "created_at": f"20{random.randint(15, 26)}-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
            })

            agent_id += 1

    # Shuffle to mix types
    random.shuffle(profiles)
    # Re-assign sequential IDs
    for i, p in enumerate(profiles):
        p["user_id"] = i

    return profiles[:n]


if __name__ == "__main__":
    profiles = generate_profiles(500)
    print(f"Generated {len(profiles)} profiles")

    # Type distribution
    from collections import Counter
    types = Counter()
    for p in profiles:
        for t in AGENT_TYPES:
            if t.replace("_", " ") in p["persona"].lower() or any(
                kw in p["persona"].lower()
                for kw in t.split("_")
            ):
                types[t] += 1
                break

    print(json.dumps(profiles[:3], indent=2, ensure_ascii=False))
