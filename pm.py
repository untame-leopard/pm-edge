#!/usr/bin/env python3
"""
pm-edge: find thin, under-researched Polymarket markets, generate research prompts,
log bets, and score your (and the AI's) calibration against the market.

Commands:
  python pm.py scan                      pull all active markets into SQLite (run hourly)
  python pm.py candidates                rank thin/stale markets worth researching
  python pm.py prompt <slug>             write a research prompt to prompts/<slug>.md
  python pm.py log --slug ... (see -h)   record a bet
  python pm.py resolve                   settle bets whose markets have closed
  python pm.py stats                     P&L, hit rate, Brier scores, calibration
"""
import argparse
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone

import requests

import config as C

UA = {"User-Agent": "pm-edge/0.1 (research)"}


# ---------------------------------------------------------------- helpers
def now_utc():
    return datetime.now(timezone.utc)


def parse_dt(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def jlist(v):
    """Gamma double-encodes lists as JSON strings."""
    if v is None:
        return []
    if isinstance(v, list):
        return v
    try:
        return json.loads(v)
    except (TypeError, ValueError):
        return []


def fnum(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def db():
    con = sqlite3.connect(C.DB_PATH)
    con.row_factory = sqlite3.Row
    con.executescript("""
    CREATE TABLE IF NOT EXISTS markets (
        id TEXT PRIMARY KEY, slug TEXT, question TEXT, description TEXT,
        outcomes TEXT, end_date TEXT, created_at TEXT, event_title TEXT,
        first_seen TEXT, last_seen TEXT
    );
    CREATE TABLE IF NOT EXISTS snapshots (
        market_id TEXT, ts TEXT, prices TEXT, best_bid REAL, best_ask REAL,
        spread REAL, liquidity REAL, volume REAL, volume24h REAL
    );
    CREATE INDEX IF NOT EXISTS ix_snap ON snapshots(market_id, ts);
    CREATE TABLE IF NOT EXISTS bets (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, slug TEXT, question TEXT,
        outcome TEXT, price REAL, stake REAL, my_prob REAL, ai_prob REAL,
        reason TEXT, result TEXT, pnl REAL, resolved_ts TEXT
    );
    """)
    return con


def get(path, params=None, retries=3):
    for i in range(retries):
        try:
            r = requests.get(f"{C.GAMMA}{path}", params=params, headers=UA, timeout=30)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            # 4xx = our request is wrong; retrying won't help
            if i == retries - 1 or (getattr(e, "response", None) is not None and 400 <= e.response.status_code < 500):
                raise
            time.sleep(2 * (i + 1))


# ---------------------------------------------------------------- scan
def _iso(dt):
    return dt.isoformat().replace("+00:00", "Z")


def _save_market(con, m, ts):
    mid = str(m.get("id"))
    ev = (m.get("events") or [{}])[0] if isinstance(m.get("events"), list) else {}
    con.execute("""
        INSERT INTO markets (id, slug, question, description, outcomes, end_date, created_at, event_title, first_seen, last_seen)
        VALUES (?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(id) DO UPDATE SET question=excluded.question, description=excluded.description,
            outcomes=excluded.outcomes, end_date=excluded.end_date, last_seen=excluded.last_seen
    """, (mid, m.get("slug"), m.get("question"), m.get("description"),
          json.dumps(jlist(m.get("outcomes"))), m.get("endDate"),
          m.get("createdAt") or m.get("startDate"), ev.get("title"), ts, ts))
    con.execute("""INSERT INTO snapshots VALUES (?,?,?,?,?,?,?,?,?)""", (
        mid, ts, json.dumps([fnum(p) for p in jlist(m.get("outcomePrices"))]),
        fnum(m.get("bestBid"), None), fnum(m.get("bestAsk"), None), fnum(m.get("spread"), None),
        fnum(m.get("liquidityNum", m.get("liquidity"))),
        fnum(m.get("volumeNum", m.get("volume"))), fnum(m.get("volume24hr"))))


def cmd_scan(_args):
    """
    Gamma limits: max 100 markets per page, and refuses offsets past ~2000 (HTTP 422).
    So we split the window [MIN_DAYS_TO_END, MAX_DAYS_TO_END] into 12-hour slices by end date
    and page through each slice separately. Each slice stays well under the offset cap.
    """
    from datetime import timedelta
    con = db()
    now = now_utc()
    ts = now.isoformat()
    SLICE_H = 12
    t0 = now + timedelta(days=C.MIN_DAYS_TO_END)
    t_end = now + timedelta(days=C.MAX_DAYS_TO_END)
    seen, capped = set(), []
    while t0 < t_end:
        t1 = min(t0 + timedelta(hours=SLICE_H), t_end)
        # Filter server-side too, so we only download thin markets (much faster than pulling everything)
        params = {"active": "true", "closed": "false", "end_date_min": _iso(t0), "end_date_max": _iso(t1),
                  "liquidity_num_min": C.MIN_LIQUIDITY, "liquidity_num_max": C.MAX_LIQUIDITY,
                  "volume_num_max": C.MAX_VOLUME,
                  "order": "endDate", "ascending": "true", "limit": 100}
        offset, before = 0, len(seen)
        for _ in range(30):                      # 30 pages = 3000 markets max per slice
            try:
                page = get("/markets", {**params, "offset": offset})
            except requests.HTTPError:
                capped.append(t0.strftime("%d %b %H:%M"))   # slice too dense; we keep what we got
                break
            if not page:
                break
            new = [m for m in page if str(m.get("id")) not in seen]
            if not new:                          # API repeating itself -> stop this slice
                break
            for m in new:
                seen.add(str(m.get("id")))
                _save_market(con, m, ts)
            con.commit()                         # save every page, so an error never loses data
            offset += len(page)
            if len(page) < 100:
                break
            time.sleep(0.1)
        print(f"  {t0.strftime('%a %d %b %H:%M')} +{SLICE_H}h: {len(seen) - before:>4} markets  (total {len(seen)})", flush=True)
        t0 = t1
    con.commit()
    print(f"[{ts[:16]}] scanned {len(seen)} markets ending in {C.MIN_DAYS_TO_END}-{C.MAX_DAYS_TO_END} days -> {C.DB_PATH}")
    if capped:
        print(f"  note: {len(capped)} slice(s) hit the API cap and were partly scanned: {', '.join(capped)}")


# ---------------------------------------------------------------- candidates
def price_movement(con, mid, hours):
    """Max abs move of any outcome price over the window, from our own snapshots. None if not enough history."""
    cutoff = datetime.fromtimestamp(now_utc().timestamp() - hours * 3600, timezone.utc).isoformat()
    rows = con.execute("SELECT ts, prices FROM snapshots WHERE market_id=? ORDER BY ts", (mid,)).fetchall()
    window = [r for r in rows if r["ts"] >= cutoff]
    if len(rows) < 2 or rows[0]["ts"] > cutoff:   # history doesn't span the window yet
        return None
    base = json.loads([r for r in rows if r["ts"] < cutoff][-1]["prices"] or "[]")
    move = 0.0
    for r in window:
        ps = json.loads(r["prices"] or "[]")
        for a, b in zip(base, ps):
            move = max(move, abs(b - a))
    return move


def cmd_candidates(args):
    con = db()
    latest = con.execute("SELECT MAX(ts) t FROM snapshots").fetchone()["t"]
    if not latest:
        sys.exit("No data yet. Run: python pm.py scan")
    rows = con.execute("""
        SELECT m.*, s.prices, s.liquidity, s.volume, s.volume24h, s.spread
        FROM markets m JOIN snapshots s ON s.market_id = m.id WHERE s.ts = ?""", (latest,)).fetchall()
    now = now_utc()
    out = []
    rej = {"excluded keyword": 0, "no end date": 0, "ends too soon/late": 0,
           "liquidity out of range": 0, "volume too high": 0, "no outcome in price band": 0}
    for r in rows:
        q = (r["question"] or "")
        if any(k in q.lower() for k in C.EXCLUDE_KEYWORDS):
            rej["excluded keyword"] += 1; continue
        end = parse_dt(r["end_date"])
        if not end:
            rej["no end date"] += 1; continue
        days = (end - now).total_seconds() / 86400
        if not (C.MIN_DAYS_TO_END <= days <= C.MAX_DAYS_TO_END):
            rej["ends too soon/late"] += 1; continue
        liq, vol = r["liquidity"] or 0, r["volume"] or 0
        if not (C.MIN_LIQUIDITY <= liq <= C.MAX_LIQUIDITY):
            rej["liquidity out of range"] += 1; continue
        if vol > C.MAX_VOLUME:
            rej["volume too high"] += 1; continue
        prices = json.loads(r["prices"] or "[]")
        outcomes = json.loads(r["outcomes"] or "[]")
        cheap = [(o, p) for o, p in zip(outcomes, prices) if C.PRICE_LO <= p <= C.PRICE_HI]
        if not cheap:
            rej["no outcome in price band"] += 1; continue
        move = price_movement(con, r["id"], C.STALE_HOURS)
        created = parse_dt(r["created_at"])
        age_days = (now - created).total_seconds() / 86400 if created else 99

        # Score: thinner, quieter, newer, sooner = more likely nobody has done the work.
        score = 0.0
        score += 2.0 * (1 - liq / C.MAX_LIQUIDITY)
        score += 1.0 * (1 - min(vol, C.MAX_VOLUME) / C.MAX_VOLUME)
        score += 1.5 * (1 - min(move, 0.10) / 0.10) if move is not None else 0.75
        score += 1.0 if age_days < 3 else 0.0
        score += 1.0 * (1 - days / C.MAX_DAYS_TO_END)
        if any(k in q.lower() for k in C.PRIORITY_KEYWORDS):
            score += C.PRIORITY_BOOST
        out.append(dict(score=score, slug=r["slug"], q=q, days=days, liq=liq, vol=vol,
                        move=move, cheap=cheap, age=age_days, event=r["event_title"] or r["slug"]))

    # Multi-outcome events (e.g. temperature buckets) are split into many binary markets.
    # Keep at most MAX_PER_EVENT per event so one event can't flood the list.
    out.sort(key=lambda d: d["score"], reverse=True)
    per_event, kept = {}, []
    for d in out:
        per_event[d["event"]] = per_event.get(d["event"], 0) + 1
        if per_event[d["event"]] <= C.MAX_PER_EVENT:
            kept.append(d)
    out = kept[: args.n]
    lines = [f"# Candidates — {latest[:16]} UTC", "",
             "| # | score | market | ends (d) | liq $ | vol $ | 48h move | cheap side |",
             "|---|---|---|---|---|---|---|---|"]
    for i, d in enumerate(out, 1):
        mv = "n/a" if d["move"] is None else f"{d['move']*100:.0f}pt"
        cheap = ", ".join(f"{o} {p*100:.0f}¢" for o, p in d["cheap"])
        lines.append(f"| {i} | {d['score']:.2f} | [{d['q'][:70]}](https://polymarket.com/market/{d['slug']}) "
                     f"| {d['days']:.1f} | {d['liq']:,.0f} | {d['vol']:,.0f} | {mv} | {cheap} |")
        print(f"{i:>2}. [{d['score']:.2f}] {d['q'][:80]}\n    {d['slug']} | ends {d['days']:.1f}d | "
              f"liq ${d['liq']:,.0f} | vol ${d['vol']:,.0f} | 48h move {mv} | {cheap}")
    with open("candidates.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nFilter funnel: {len(rows)} markets in latest scan")
    for k, v in rej.items():
        print(f"  - {v:>5} dropped: {k}")
    print(f"\n{len(out)} candidates -> candidates.md   Next: python pm.py prompt <slug>")


# ---------------------------------------------------------------- prompt
PROMPT = """You are an expert forecaster. Research this prediction market question and estimate the probability of each outcome.

## Question
{question}

## Resolution rules (READ CAREFULLY — the market resolves on these exact rules, not on the headline)
{rules}

- Market closes: {end}
- Outcomes: {outcomes}
- Today: {today}

## What to research
{hints}
Search for the most recent, primary sources. Note the publication date of everything you cite.
Do NOT look up or consider the current Polymarket price or any other betting odds — I need an independent estimate.

## Output (exactly this format)
1. **Resolution check:** In one or two sentences, what exactly has to happen for each outcome, per the rules above. Flag any ambiguity.
2. **Key evidence:** 3–7 bullets, each with source name, date, and link.
3. **Base rate:** What's the historical frequency for comparable situations, and how did you get it?
4. **Probabilities:** One line per outcome, e.g. `Yes: 0.72`. They must sum to 1.
5. **Confidence:** low / medium / high, with one sentence why.
6. **What would make this wrong:** The single most likely way your estimate fails.
"""


def cmd_prompt(args):
    con = db()
    r = con.execute("SELECT * FROM markets WHERE slug=?", (args.slug,)).fetchone()
    if not r:
        sys.exit(f"Slug not found in DB: {args.slug} (run scan first)")
    q = r["question"] or ""
    hints = [h for k, h in C.CATEGORY_HINTS.items() if k in q.lower()]
    hints_txt = ("\n".join(f"- {h}" for h in hints) + "\n") if hints else \
        "- The facts that most directly determine the outcome, and the exact source the market resolves on.\n"
    text = PROMPT.format(question=q, rules=(r["description"] or "(no rules text — check the market page)").strip(),
                         end=r["end_date"], outcomes=", ".join(json.loads(r["outcomes"] or "[]")),
                         today=now_utc().strftime("%Y-%m-%d"), hints=hints_txt)
    os.makedirs("prompts", exist_ok=True)
    path = os.path.join("prompts", f"{args.slug}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    snap = con.execute("SELECT prices FROM snapshots WHERE market_id=? ORDER BY ts DESC LIMIT 1", (r["id"],)).fetchone()
    print(text)
    print(f"--- saved to {path}. Market price (hidden from the AI on purpose): "
          f"{dict(zip(json.loads(r['outcomes'] or '[]'), json.loads(snap['prices'] or '[]')))}")


# ---------------------------------------------------------------- bet log
def cmd_log(args):
    con = db()
    r = con.execute("SELECT question FROM markets WHERE slug=?", (args.slug,)).fetchone()
    con.execute("""INSERT INTO bets (ts, slug, question, outcome, price, stake, my_prob, ai_prob, reason)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (now_utc().isoformat(), args.slug, r["question"] if r else None, args.outcome,
                 args.price, args.stake, args.prob, args.ai_prob, args.reason))
    con.commit()
    edge = (args.prob - args.price) * 100
    print(f"Logged: {args.outcome} @ {args.price*100:.0f}¢, stake {args.stake}, your p={args.prob:.2f} (edge {edge:+.0f}pt)")


def cmd_resolve(_args):
    con = db()
    open_bets = con.execute("SELECT * FROM bets WHERE result IS NULL").fetchall()
    for b in open_bets:
        data = get("/markets", {"slug": b["slug"]})
        if not data:
            print(f"? {b['slug']}: not found")
            continue
        m = data[0]
        if not m.get("closed"):
            continue
        outcomes = jlist(m.get("outcomes"))
        prices = [fnum(p) for p in jlist(m.get("outcomePrices"))]
        if not prices or max(prices) < 0.99:
            print(f"? {b['slug']}: closed but not cleanly resolved yet {prices}")
            continue
        winner = outcomes[prices.index(max(prices))]
        won = winner.lower() == (b["outcome"] or "").lower()
        pnl = b["stake"] / b["price"] - b["stake"] if won else -b["stake"]
        con.execute("UPDATE bets SET result=?, pnl=?, resolved_ts=? WHERE id=?",
                    ("win" if won else "loss", pnl, now_utc().isoformat(), b["id"]))
        print(f"{'WIN ' if won else 'LOSS'} {pnl:+.2f}  {b['question'] or b['slug']}")
    con.commit()


def brier(pairs):
    return sum((p - y) ** 2 for p, y in pairs) / len(pairs) if pairs else None


def cmd_stats(_args):
    con = db()
    bets = con.execute("SELECT * FROM bets WHERE result IS NOT NULL").fetchall()
    n_open = con.execute("SELECT COUNT(*) c FROM bets WHERE result IS NULL").fetchone()["c"]
    if not bets:
        sys.exit(f"No resolved bets yet ({n_open} open).")
    y = [1 if b["result"] == "win" else 0 for b in bets]
    staked = sum(b["stake"] for b in bets)
    pnl = sum(b["pnl"] for b in bets)
    print(f"Resolved: {len(bets)}  (open: {n_open})")
    print(f"Hit rate: {sum(y)/len(y):.1%}   avg price paid: {sum(b['price'] for b in bets)/len(bets):.1%}  "
          f"(you need hit rate > avg price to profit)")
    print(f"P&L: {pnl:+.2f} on {staked:.2f} staked  ROI {pnl/staked:+.1%}")
    print("\nBrier score (lower = better; this is the CV number):")
    print(f"  market price: {brier([(b['price'], t) for b, t in zip(bets, y)]):.4f}")
    print(f"  you:          {brier([(b['my_prob'], t) for b, t in zip(bets, y)]):.4f}")
    ai = [(b["ai_prob"], t) for b, t in zip(bets, y) if b["ai_prob"] is not None]
    if ai:
        print(f"  AI:           {brier(ai):.4f}   (n={len(ai)})")
    print("\nCalibration (your prob):")
    for lo in (0.0, 0.2, 0.4, 0.6, 0.8):
        grp = [t for b, t in zip(bets, y) if lo <= b["my_prob"] < lo + 0.2 or (lo == 0.8 and b["my_prob"] == 1.0)]
        if grp:
            print(f"  said {lo:.0%}-{lo+0.2:.0%}: won {sum(grp)}/{len(grp)} = {sum(grp)/len(grp):.0%}")
    if len(bets) < 30:
        print(f"\n(n={len(bets)} — too small to conclude anything. Aim for 30+, ideally 100.)")


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("scan").set_defaults(f=cmd_scan)
    c = sub.add_parser("candidates"); c.add_argument("-n", type=int, default=C.TOP_N); c.set_defaults(f=cmd_candidates)
    p = sub.add_parser("prompt"); p.add_argument("slug"); p.set_defaults(f=cmd_prompt)
    l = sub.add_parser("log", help="record a bet")
    l.add_argument("--slug", required=True)
    l.add_argument("--outcome", required=True, help='outcome you bought, e.g. "Yes" or "No"')
    l.add_argument("--price", type=float, required=True, help="price paid, 0-1 (17c = 0.17)")
    l.add_argument("--stake", type=float, required=True)
    l.add_argument("--prob", type=float, required=True, help="YOUR final probability for that outcome")
    l.add_argument("--ai-prob", type=float, default=None, help="the AI's probability for that outcome")
    l.add_argument("--reason", default="")
    l.set_defaults(f=cmd_log)
    sub.add_parser("resolve").set_defaults(f=cmd_resolve)
    sub.add_parser("stats").set_defaults(f=cmd_stats)
    args = ap.parse_args()
    args.f(args)


if __name__ == "__main__":
    main()