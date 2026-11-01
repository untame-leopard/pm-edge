# pm-edge: project context (handoff, Nov 1 2026)

## What this is
Find thin, under-researched Polymarket markets; research them with an LLM (Gemini Deep Research) with the market
price hidden; bet only on large, verified edges; log everything; measure calibration (Brier: me vs AI vs market).
CV framing: "measured LLM forecasting calibration against prediction-market prices in low-liquidity markets".

## Daily loop
scan (hourly via Task Scheduler, pythonw.exe) → `python pm.py candidates` → `python pm.py prompt <slug>` →
paste into Gemini → read the market rules myself → verify key numbers at T1 sources → decide per RULES.md →
`python pm.py log ...` if betting → a line in notes.md either way → commit.

## Thresholds (why)
- Judgement markets: bet only if (my prob − ask) ≥ 15pt. My estimate is noisy and I only bet when I disagree with
  the market (selection bias). Shrinkage view: true ≈ w·mine + (1−w)·market, w≈0.4 untested → 15pt raw ≈ 6pt real,
  which survives a 1–2¢ spread. Revisit after 30+ resolved bets using `stats` (my Brier vs market's).
- Arithmetic markets (e.g. a Rotten Tomatoes score with its review count, where the outcome is nearly locked): 5pt.

## Findings so far (week 1)
1. Gemini inflates longshots past its own evidence in 3 of 3 runs (Wildwood 15% vs ~10%; Clayface 34% vs its own 23%
   base; MrBeast 28% vs its own 8% base). → Use its base rate, not its final number. Log both.
2. Gemini presents unofficial figures (Koimoi, r/boxoffice) as fact. → The prompt now forces T1/T2/T3 source tags.
3. Gemini mixes reference classes (Trump crypto: counted crypto-themed WH events alongside rallies; rallies were 0/9).
   → The prompt now forces base rate → signed adjustments → arithmetic, and a matching reference class.
4. Markets researched so far were mostly fairly priced (0 bets in week 1). Edges are rare; most research ends in a skip.

## Categories
- Good (researchable): box office (buckets as % drop from opening; previews inflate the opening; check The Numbers
  dailies), Trump/earnings-call "say X" (count transcripts), YouTube views (recent day-1 distribution), Rotten Tomatoes
  (review-count arithmetic: fresh = pct × n; how many straight fresh/rotten to cross the threshold; RT rounds the
  displayed %). For multi-bucket events: one research run per event, full distribution, compare to every bucket.
- Excluded in config: crypto up/down, asset price thresholds (priced off options), sports props, weather.

## Technical notes
- Gamma API: max 100 markets per page; offsets past ~2100 return 422. The scan pages through 12h end-date slices over
  0.5–21 days, with server-side liquidity/volume filters.
- Candidate score: thin liquidity (2) + low volume (1) + stale 48h price (1.5) + new (1) + ends soon (1) + priority
  keyword (2). It's a ranking, not a probability.

## Parked ideas
- Options-implied fair value for stock-threshold markets (lognormal / barrier probability) — a quant module for the CV.
- Market making in empty buckets (post limit orders). Later.
- Automating research via the API once calibration shows it's worth paying for.
