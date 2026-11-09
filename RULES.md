# Rules

## Before betting
- Read the market's resolution rules myself. Don't rely on the AI's summary.
- Check the reference class matches the event type (e.g. rallies vs crypto events).
- Verify the 1-2 numbers the estimate hinges on at a T1/T2 source.
- 2-min triage before running Gemini: one search for the current public consensus. If the market already matches it, skip without a research run.
- Box office: use only release-week previews (Boxoffice Pro weekend preview, Deadline/Variety), never long-range tracking.
- Use Gemini's base rate, not its final number. It inflates longshots (3/3 runs). Log both.

## Edge and sizing
- Shrink first: q = 0.4 × my prob + 0.6 × market ask (w untested; revisit after 30+ resolved forecasts via `stats`, bets vs skips).
- Bet only if expected return after fees ≥ 10%: q / ask − 1 − fee ≥ 0.10.
- Size by quarter-Kelly: stake = 0.25 × (q − ask) / (1 − ask) × bankroll, capped at 2% of bankroll.
- Arithmetic markets (outcome nearly locked, e.g. RT score + review count): skip shrinkage, same 10% return test.
- Replaced the 15pt/5pt point thresholds on 2026-11-09: a point gap ignores price (6pt at 17¢ ≈ +35%, at 76¢ ≈ +8%).

## Always
- Every market researched gets a row: `pm.py forecast` (skip) or `pm.py log` (bet). Plus a line in notes.md.
