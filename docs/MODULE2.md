# Module 2: BTC 15-minute up/down markets as digital options

Main focus from Nov 2026. Module 1 (LLM-researched thin markets) runs on autopilot alongside.

## Idea
Each market pays $1 if BTC ends the 15-minute window above the start price K. Treat it as a cash-or-nothing digital
option and price it with a driftless random walk:

    P(up) = Φ( ln(S/K) / (σ√τ) )

with S the current price, τ the time left and σ from recent realised volatility. The full Black-Scholes d2 has an extra
−σ²τ/2 term; at τ ≤ 15 min it is negligible (~1e-6 in log terms), so it is dropped on purpose.

At the window open S = K, so the model says 0.50 by construction. All the information arrives mid-window, so every
analysis is binned by τ.

The model is the fair-value reference. The interesting questions are about the market around it (see QT angle).

## Known headwinds
- The most bot-crowded markets on Polymarket. The real edge there is latency, which I can't win.
- Taker fees since Jan 2026 (reportedly up to ~3%, highest at 50¢, funding maker rebates). **Verify the current fee formula.**
- GBM understates short-horizon tails.

## Hypotheses
- (a) Mispricing at the extremes (3–5¢ / 95–97¢): low fees there, possible longshot bias.
- (b) Maker-side quoting earns spread + rebates, net of adverse selection. Paper-trade only: an honest backtest needs
  queue position and fill data I won't have.
- (c) Gaps between the resolution price feed and the exchange price. **Check which feed resolves these markets**
  (believed to be Chainlink BTC/USD, not Binance). S and σ must come from the same feed the market resolves on.
- (d) Slow repricing after volatility regime changes.

## QT angle (the part interviewers care about)
- **Lag:** after BTC moves, how many seconds until the Polymarket mid catches up? Are quotes stale?
- **Spread and depth over the window:** how do they behave as τ → 0 and near the strike? Where does liquidity vanish?
- **Maker P&L with adverse selection:** spread + rebate earned vs. losses from being filled when wrong.

## Phases
Each phase ≈ 1–2 short sessions.

0. **Order-book recorder (start day 1).** Historical `prices-history` gives last-trade/mid at ~1-min resolution, not
   bid/ask, so ask-based backtests on old data are impossible. Record live: CLOB websocket → SQLite, best bid/ask +
   size every few seconds for every active BTC 15-min market. ~96 markets/day, so 1,000 markets with real books ≈ 10 days.
   Done when: recorder runs unattended and survives disconnects.
1. **Historical data.** Resolved BTC 15-min markets (Gamma), their CLOB `prices-history` at finest resolution, outcomes,
   strike/start price, exact resolution source and timestamp from the rules, plus 1-min BTC klines from the resolution
   feed (or the closest proxy). Store in SQLite.
   Done when: ≥1,000 resolved markets with time-aligned market price + BTC price paths.
2. **Model.** For every (market, minute): τ, S/K, σ from trailing realised vol (EWMA of 1-min returns, past data only),
   model probability. Variants: Normal vs Student-t vs empirical bootstrap of recent returns; σ with and without
   intraday seasonality (US open vs 3am).
   Done when: model_prob columns exist for all rows.
3. **Calibration.** Model vs market vs outcome: Brier / log-loss, reliability plots, binned by price level and τ.
   Uses historical mid (fine for calibration, not for P&L).
   Done when: tables and charts showing where, if anywhere, the model beats the market.
4. **Fee-adjusted backtest (recorded books only).** Simulated taker trades at the ASK + fee when |model − ask| > threshold;
   bootstrap CIs. Crude maker simulation, clearly labelled as optimistic.
   Done when: P&L by bucket with CIs and n.
5. **Decision.** If an edge survives fees in a specific bucket (large n, CI excludes 0): 2 weeks of live paper trading,
   then only a small bot with hard limits. Otherwise: write it up. "No edge after fees, here's where the market is
   efficient and why" is still a strong result.

## Pitfalls
- Mid instead of ask.
- Look-ahead in σ.
- Timestamp misalignment (seconds matter; store everything in UTC with ms).
- Ignoring fees.
- Overfitting thresholds on the same data: hold out the most recent 30%.
- Modelling a different price feed from the one the market resolves on.

## Split (two people)
- Person A: recorder + historical data pipeline (phases 0–1).
- Person B: model + calibration (phases 2–3).
- Both: backtest and write-up. Code lives in `btc/` in this repo.
