# Rules

## Before betting
- Read the market's resolution rules myself. Don't rely on the AI's summary.
- Check the reference class matches the event type (e.g. rallies vs crypto events).
- Verify the 1-2 numbers the estimate hinges on at a T1/T2 source.
- 2-min triage before running Gemini: one search for the current public consensus. If the market already matches it, skip without a research run.
- Box office: use only release-week previews (Boxoffice Pro weekend preview, Deadline/Variety), never long-range tracking.
- Use Gemini's base rate, not its final number. It inflates longshots (3/3 runs). Log both.

## Edge threshold (my prob − ask)
- Judgement markets: ≥ 15pt. Shrinkage w≈0.4 → ~6pt real, which survives the spread.
- Arithmetic markets (e.g. RT score + review count, outcome nearly locked): ≥ 5pt.
- Revisit after 30+ resolved bets using `stats`.

## Always
- Every market researched gets a row: `pm.py forecast` (skip) or `pm.py log` (bet). Plus a line in notes.md.
