"""Tunable settings. Keep your real thresholds here (and out of public commits if they start working)."""

DB_PATH = "pm_edge.db"
GAMMA = "https://gamma-api.polymarket.com"

# ---- Candidate filter ----
MIN_DAYS_TO_END = 0.5      # too close = no time to research
MAX_DAYS_TO_END = 21       # too far = capital locked up
MIN_LIQUIDITY = 300        # need *some* book to trade into ($)
MAX_LIQUIDITY = 25_000     # thin markets are the whole thesis
MAX_VOLUME = 150_000       # skip heavily traded markets
PRICE_LO = 0.05            # look for an outcome priced in this band:
PRICE_HI = 0.40            # cheap enough that being right pays well
STALE_HOURS = 48           # "nobody's looking" = price barely moved in this window
TOP_N = 25
MAX_PER_EVENT = 2          # max candidates shown from the same event (e.g. temperature buckets)

# Skip high-frequency / bot-dominated or unresearchable stuff (case-insensitive substring match on question)
EXCLUDE_KEYWORDS = [
    "up or down", "price of bitcoin", "price of ethereum", "price of solana",
    "bitcoin above", "ethereum above", "solana above", "xrp above",
    " vs. ", " vs ", "o/u", "spread:",
    # weather: modelled by bots with free forecast data, a separate project if ever
    "highest temperature", "lowest temperature", "will it rain", "inches of rain", "snow in",
    # asset price thresholds: priced off options/futures by pros, research gives no edge
    "close above", "closes above", "close below", "closes below", "hit (low)", "hit (high)",
    "(xauusd)", "(xagusd)", "(wti)",
    # sports: priced off sportsbooks
    "halftime", "touchdown", "2+ ", " win on 20", "both teams to score", "exact score", "draw on 20",
]

# Categories where research has a real chance of beating the price. Matches get a score boost
# so they rise to the top. Add categories here as your bet log shows where you're good.
PRIORITY_KEYWORDS = ["box office", "will trump say", " say \"", "views", "mrbeast", "rotten tomatoes",
                     "metacritic", "billboard", "spotify", "tweet", "mention", "earnings"]
PRIORITY_BOOST = 2.0

# Category-specific research hints, added to the prompt when the keyword appears in the question
CATEGORY_HINTS = {
    "box office": "Find: latest industry tracking (Deadline, Variety, BoxOfficePro, Boxoffice Theory), Thursday preview grosses, "
                  "theatre count, comparable films' openings, and EXACTLY which source and figure (domestic? weekend? 3-day?) resolves the market.",
    "metacritic": "Find: review embargo date, number of reviews already in, early aggregate scores (OpenCritic), the developer's "
                  "historical scores, and which platform's Metascore resolves the market.",
    "rotten tomatoes": "Find: current score and review count if reviews are out, festival reactions, director's history, "
                       "and whether Tomatometer or Popcornmeter resolves it.",
    "billboard": "Find: streaming/sales tracking (HitsDailyDouble projections), competition that week, chart week dates.",
    "spotify": "Find: current daily stream counts (kworb.net), trajectory, release-day spikes, exact chart/date used.",
    "election": "Find: latest polls with dates and sample sizes, polling averages, historical polling error, early vote data.",
    "temperature": "Find: the exact resolving weather station, latest model forecasts (ECMWF/GFS), and observations so far.",
    "tweet": "Find: the account's recent posting rate, counting rules (replies? reposts?), and the exact counting window.",
}