import argparse
import csv
import datetime as dt
import math
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nclh_mc.market import implied_vol

FIELDS = ["strike", "call_bid", "call_ask", "put_bid", "put_ask", "call_oi", "put_oi"]


def _num(x):
    x = (x or "").strip().replace("$", "").replace(",", "")
    if x in ("", "-", "--", "N/A", "n/a"):
        return None
    return float(x)


def read_raw(path):
    with open(path, newline="") as f:
        lines = [ln for ln in f if ln.strip() and not ln.lstrip().startswith("#")]
    rows = []
    for rec in csv.DictReader(lines):
        rec = {k.strip().lower(): v for k, v in rec.items() if k}
        missing = [c for c in FIELDS[:5] if c not in rec]
        if missing:
            raise SystemExit(f"Missing columns {missing}. Use the header in data/raw_quotes_TEMPLATE.csv.")
        row = {c: _num(rec.get(c)) for c in FIELDS}
        if row["strike"] is not None:
            rows.append(row)
    rows.sort(key=lambda r: r["strike"])
    return rows


def mid_or_reason(bid, ask, oi, max_spread, min_oi):
    if ask is None:
        return None, "no ask"
    if bid is None or bid <= 0:
        return None, "no bid"
    if ask < bid:
        return None, "ask below bid"
    mid = 0.5 * (bid + ask)
    if (ask - bid) > 0.10 and (ask - bid) / mid > max_spread:
        return None, f"spread {(ask - bid) / mid:.0%} of mid"
    if min_oi and (oi is None or oi < min_oi):
        return None, f"open interest {0 if oi is None else int(oi)} < {min_oi}"
    return mid, None


def arbitrage_violations(strikes, prices, kind, disc):
    bad = []
    pts = [(k, p) for k, p in zip(strikes, prices) if p is not None]
    for (k1, p1), (k2, p2) in zip(pts, pts[1:]):
        slope = (p2 - p1) / (k2 - k1)
        if kind == "call" and not (-disc - 1e-9 <= slope <= 1e-9):
            bad.append(f"call {k1:g}->{k2:g} ({p1:.2f} -> {p2:.2f})")
        if kind == "put" and not (-1e-9 <= slope <= disc + 1e-9):
            bad.append(f"put {k1:g}->{k2:g} ({p1:.2f} -> {p2:.2f})")
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("raw", help="raw quotes CSV (see data/raw_quotes_TEMPLATE.csv)")
    ap.add_argument("--spot", type=float, required=True, help="share price on the pricing date")
    ap.add_argument("--expiry", required=True, help="YYYY-MM-DD")
    ap.add_argument("--market-config", default="market_config.toml")
    ap.add_argument("--rate", type=float)
    ap.add_argument("--pricing-date")
    ap.add_argument("--max-spread", type=float, default=0.5, help="max (ask-bid)/mid, default 0.5")
    ap.add_argument("--min-oi", type=int, default=0, help="minimum open interest, default 0 (off)")
    ap.add_argument("--out")
    args = ap.parse_args()

    mcfg = {}
    if Path(args.market_config).exists():
        with open(args.market_config, "rb") as f:
            mcfg = tomllib.load(f)
    r = args.rate if args.rate is not None else mcfg.get("risk_free_rate")
    pdate = args.pricing_date or mcfg.get("pricing_date")
    if r is None or pdate is None:
        raise SystemExit("Need --rate and --pricing-date (or a market_config.toml with them).")
    T = (dt.date.fromisoformat(args.expiry) - dt.date.fromisoformat(pdate)).days / 365.25
    disc = math.exp(-r * T)
    S = args.spot

    rows = read_raw(args.raw)
    if len(rows) < 3:
        raise SystemExit("Fewer than three strikes in the raw file.")

    out_rows, dropped = [], []
    for row in rows:
        cm, cr = mid_or_reason(row["call_bid"], row["call_ask"], row["call_oi"], args.max_spread, args.min_oi)
        pm, pr = mid_or_reason(row["put_bid"], row["put_ask"], row["put_oi"], args.max_spread, args.min_oi)
        if cr:
            dropped.append(f"call {row['strike']:g}: {cr}")
        if pr:
            dropped.append(f"put {row['strike']:g}: {pr}")
        out_rows.append((row["strike"], cm, pm))

    strikes = [k for k, _, _ in out_rows]
    issues = arbitrage_violations(strikes, [c for _, c, _ in out_rows], "call", disc)
    issues += arbitrage_violations(strikes, [p for _, _, p in out_rows], "put", disc)

    # put-call parity
    implied_spots = [c - p + k * disc for k, c, p in out_rows
                     if c is not None and p is not None and abs(k / S - 1) <= 0.2]
    parity_note = "no strike near the money has both a call and a put mid"
    parity_off = False
    if implied_spots:
        s_imp = sum(implied_spots) / len(implied_spots)
        parity_off = abs(s_imp / S - 1) > 0.02
        parity_note = f"implied share price ${s_imp:.2f} vs. ${S:.2f}"

    usable_lo = min([k for k, c, p in out_rows if (p if k < S else c) is not None], default=float("nan"))
    usable_hi = max([k for k, c, p in out_rows if (p if k < S else c) is not None], default=float("nan"))
    need_lo, need_hi = 0.45 * S, 2.15 * S

    atm = min(out_rows, key=lambda x: abs(x[0] - S))
    ivs = []
    if atm[1] is not None:
        ivs.append(implied_vol(atm[1], S, atm[0], T, r, "call"))
    if atm[2] is not None:
        ivs.append(implied_vol(atm[2], S, atm[0], T, r, "put"))
    ivs = [v for v in ivs if not math.isnan(v)]

    out = Path(args.out or f"data/nclh_chain_{args.expiry}.csv")
    with open(out, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["strike", "call_mid", "put_mid"])
        for k, c, p in out_rows:
            w.writerow([f"{k:g}", "" if c is None else f"{c:.4f}", "" if p is None else f"{p:.4f}"])

    print(f"Expiry {args.expiry}: {T:.2f} years from {pdate}. Rate {r:.2%}. Spot ${S:.2f}.")
    print(f"Strikes read: {len(rows)}. Quotes dropped: {len(dropped)}.")
    for d in dropped:
        print("  dropped", d)
    print(f"Usable out-of-the-money strikes: ${usable_lo:g} to ${usable_hi:g} "
          f"(the comparison needs roughly ${need_lo:.2f} to ${need_hi:.2f})")
    if not (usable_lo <= need_lo and usable_hi >= need_hi):
        print("  WARNING: coverage gap. Some comparison rows will show n/a.")
    print(f"Put-call parity: {parity_note}")
    if parity_off:
        print("  WARNING: more than 2% off. Quotes are probably not from the pricing date, or are stale.")
    if issues:
        print(f"No-arbitrage violations ({len(issues)}), usually stale or one-sided quotes:")
        for i in issues:
            print("  ", i)
        print("  Fix or blank those quotes before using the file.")
    else:
        print("No-arbitrage checks passed.")
    if ivs:
        print(f"At-the-money implied vol at ${atm[0]:g}: {sum(ivs) / len(ivs):.1%} "
              "-> use for implied_vol.one_year_atm in market_config.toml")
    if abs(T - 1) > 0.25:
        print("WARNING: expiry is more than three months from the 12-month horizon.")
    print(f"\nWrote {out}. Point market_config.toml [option_chain] path and expiry at it.")
    if issues or parity_off:
        sys.exit(2)


if __name__ == "__main__":
    main()
