# pm-edge

Finds thin, under-researched Polymarket markets, generates research prompts for an LLM (with the market price deliberately hidden from it), logs bets, and scores forecast calibration against the market.

**Question this project answers:** can AI-assisted research beat prediction-market prices in low-liquidity markets, net of costs?

## Setup
```
pip install -r requirements.txt
python pm.py scan
```

## Daily loop
```
python pm.py scan                 # also runs hourly via Task Scheduler (below)
python pm.py candidates           # ranked shortlist -> candidates.md
python pm.py prompt <slug>        # paste prompts/<slug>.md into Gemini Deep Research
python pm.py log --slug <slug> --outcome Yes --price 0.17 --stake 10 --prob 0.70 --ai-prob 0.75 --reason "tracking says 9M+"
python pm.py resolve              # settles closed markets
python pm.py stats                # hit rate, ROI, Brier: you vs AI vs market
```
**Log every bet you take, including the AI's probability.** The stats are only as honest as the log.

## Run the scanner hourly (Windows)
Task Scheduler → Create Basic Task → Daily → Action "Start a program":
- Program: `python` (or the full path from `where python`)
- Arguments: `pm.py scan`
- Start in: this folder

Then Properties → Triggers → Edit → "Repeat task every 1 hour" for "Indefinitely".

The 48h-movement signal needs 2 days of hourly snapshots before it kicks in.

## Tuning
All thresholds are in `config.py`: liquidity and volume caps, days to resolution, price band, and excluded keywords.

## Results
_(fill in after 30+ resolved bets: n, hit rate vs avg price, ROI, Brier for market / you / AI, calibration plot, what didn't work)_
