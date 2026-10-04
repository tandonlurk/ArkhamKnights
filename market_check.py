import argparse
import datetime as dt
import json
import math
import tomllib
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from nclh_mc.inputs import load_inputs
from nclh_mc.market import (
    chain_prob_above, conditional_probs, expected_value, gbm_prob_above, implied_vol,
    implied_weight, interp_prob_above, load_chain, model_prob, thresholds,
)
from nclh_mc.model import point_expected_value, point_targets
from nclh_mc.simulate import simulate


def pct(x):
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.1%}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="config.toml")
    ap.add_argument("--market-config", default="market_config.toml")
    ap.add_argument("--workbook")
    ap.add_argument("--iv", type=float, help="1-year at-the-money implied vol, e.g. 0.58")
    ap.add_argument("--rate", type=float, help="risk-free rate, e.g. 0.041")
    ap.add_argument("--chain", help="option chain CSV (empty string to skip)")
    ap.add_argument("--expiry", help="chain expiry, YYYY-MM-DD")
    ap.add_argument("--out", default="results")
    args = ap.parse_args()

    with open(args.config, "rb") as f:
        cfg = tomllib.load(f)
    with open(args.market_config, "rb") as f:
        mcfg = tomllib.load(f)

    iv = args.iv if args.iv is not None else mcfg["implied_vol"]["one_year_atm"]
    r = args.rate if args.rate is not None else mcfg["risk_free_rate"]
    q = mcfg.get("dividend_yield", 0.0)
    mu = mcfg["real_world_drift"]
    chain_path = mcfg["option_chain"]["path"] if args.chain is None else args.chain
    expiry = args.expiry or mcfg["option_chain"]["expiry"]
    pricing_date = dt.date.fromisoformat(mcfg["pricing_date"])

    warnings = []

    inp = load_inputs(args.workbook or cfg["workbook"])
    point = point_targets(inp)
    for s, t in point.items():
        if abs(t - inp.excel_targets[s]) > 0.01:
            raise SystemExit(f"Python replica no longer matches the workbook ({s}). Fix nclh_mc/model.py first.")
    S = inp.share_price
    price, scen, names = simulate(inp, cfg)
    weights = dict(inp.probabilities)
    scen_means = {n: float(price[scen == i].mean()) for i, n in enumerate(names)}

    T_iv = 1.0
    chain = None
    if chain_path:
        T_chain = (dt.date.fromisoformat(expiry) - pricing_date).days / 365.25
        strikes, calls, puts = load_chain(chain_path)
        mids, probs = chain_prob_above(strikes, calls, puts, S, T_chain, r, q)
        atm = int(np.argmin(np.abs(strikes - S)))
        atm_iv = implied_vol(float(calls[atm]), S, float(strikes[atm]), T_chain, r, "call", q)
        chain = {"T": T_chain, "mids": mids, "probs": probs, "atm_iv": atm_iv, "path": chain_path}
        if abs(T_chain - 1) > 0.25:
            warnings.append(f"Chain expiry is {T_chain:.2f} years out, not 12 months. "
                            "Its probabilities cover a different horizon than the model.")

    rows = []
    for label, level, side in thresholds(S, point):
        def market(p_above):
            return p_above if side == "above" else 1 - p_above
        row = {
            "event": label, "level": level, "side": side,
            "model": model_prob(price, level, side),
            "gbm_risk_neutral": float(market(gbm_prob_above(S, level, T_iv, r, iv))),
            "gbm_real_world": float(market(gbm_prob_above(S, level, T_iv, mu, iv))),
            "chain": float("nan"),
        }
        if chain:
            pa = interp_prob_above(chain["mids"], chain["probs"], level)
            row["chain"] = float("nan") if math.isnan(pa) else market(pa)
        rows.append(row)

    source = "chain" if chain and abs(chain["T"] - 1) <= 0.25 else "gbm_risk_neutral"
    by_event = {r_["event"]: r_ for r_ in rows}
    up, down = by_event["Gain more than half"], by_event["Lose more than half"]

    cond_up = conditional_probs(price, scen, names, up["level"], "above")
    w_bull, clamp_bull = implied_weight(cond_up, weights, up[source], "bull", "base", "bear")
    w_up = dict(weights, bull=w_bull, base=weights["bull"] + weights["base"] - w_bull)

    cond_dn = conditional_probs(price, scen, names, down["level"], "below")
    w_bear, clamp_bear = implied_weight(cond_dn, weights, down[source], "bear", "base", "bull")
    w_dn = dict(weights, bear=w_bear, base=weights["bear"] + weights["base"] - w_bear)

    implied = {
        "source": source,
        "bull_weight_matching_upside": w_bull, "bull_clamped": clamp_bull,
        "ev_at_bull_weight": expected_value(w_up, scen_means),
        "bear_weight_matching_downside": w_bear, "bear_clamped": clamp_bear,
        "ev_at_bear_weight": expected_value(w_dn, scen_means),
        "ev_current_weights": expected_value(weights, scen_means),
    }

    for w in warnings:
        print("WARNING:", w)
    print(f"\n{'Event':34s} {'Model':>7s} {'GBM rn':>7s} {'GBM rw':>7s} {'Chain':>7s}")
    for r_ in rows:
        print(f"{r_['event']:34s} {pct(r_['model']):>7s} {pct(r_['gbm_risk_neutral']):>7s} "
              f"{pct(r_['gbm_real_world']):>7s} {pct(r_['chain']):>7s}")
    print(f"\nTo match the market's upside ({source}), bull weight would be {w_bull:.0%} "
          f"(now {weights['bull']:.0%}); target ${implied['ev_at_bull_weight']:.2f}")
    print(f"To match the market's downside ({source}), bear weight would be {w_bear:.0%} "
          f"(now {weights['bear']:.0%}); target ${implied['ev_at_bear_weight']:.2f}")

    out = Path(args.out)
    out.mkdir(exist_ok=True)
    chart(price, S, iv, r, mu, chain, point, warnings, out / "market_vs_model.png")
    write_markdown(out / "market_check.md", warnings, S, iv, r, mu, chain, rows, weights,
                   point_expected_value(inp), implied)
    with open(out / "market_check.json", "w") as f:
        json.dump({"inputs": {"implied_vol": iv, "risk_free_rate": r, "real_world_drift": mu,
                              "chain": chain_path or None,
                              "chain_years": chain["T"] if chain else None,
                              "chain_atm_iv": chain["atm_iv"] if chain else None},
                   "warnings": warnings, "rows": rows, "implied_weights": implied}, f, indent=2)
    print(f"\nResults written to {out}/")


def chart(price, S, iv, r, mu, chain, point, warnings, path):
    x = np.linspace(0.25, 45, 400)
    srt = np.sort(price)
    model_above = 1 - np.searchsorted(srt, x, side="right") / len(srt)
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(x, model_above * 100, color="#2E6F95", lw=2.2, label="Our model (simulation)")
    ax.plot(x, gbm_prob_above(S, x, 1.0, r, iv) * 100, color="#8A8F98", lw=1.6,
            label=f"GBM, {iv:.0%} implied vol (risk-neutral)")
    ax.plot(x, gbm_prob_above(S, x, 1.0, mu, iv) * 100, color="#8A8F98", lw=1.2, ls="--",
            label=f"GBM, {mu:.0%} expected return")
    if chain:
        ax.plot(chain["mids"], chain["probs"] * 100, "o-", color="#B23A48", ms=4, lw=1.2,
                label="Option chain implied")
    ax.axvline(S, color="black", lw=1)
    ax.text(S, 101, f"Share price ${S:.2f}", ha="center", va="bottom", fontsize=9)
    ax.axvline(point["bull"], color="black", lw=0.8, ls=":")
    ax.text(point["bull"], 101, f"Bull target ${point['bull']:.2f}", ha="center", va="bottom", fontsize=9)
    ax.set_xlim(0, 45)
    ax.set_ylim(0, 100)
    ax.set_xlabel("12-month price ($)")
    ax.set_ylabel("Chance the stock ends above this price (%)")
    ax.set_title("Our model vs. the options market", loc="left", fontsize=12, pad=22)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, fontsize=9, loc="upper right")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def write_markdown(path, warnings, S, iv, r, mu, chain, rows, weights, point_ev, imp):
    L = ["# Market cross-check: options-implied probabilities vs. our model\n"]
    for w in warnings:
        L.append(f"> **Warning:** {w}\n")
    L.append(f"Share price ${S:.2f}. Single implied vol {iv:.0%}, risk-free rate {r:.1%}, "
             f"real-world drift {mu:.0%}, horizon 1 year.")
    if chain:
        L.append(f" Option chain: `{chain['path']}`, {chain['T']:.2f} years to expiry, "
                 f"at-the-money implied vol from the chain {chain['atm_iv']:.0%}.")
    L.append("\n")
    L.append("## Probabilities\n")
    L.append("GBM: lognormal, single implied vol. Chain: risk-neutral, Breeden-Litzenberger across strikes.\n")
    L.append("| Event | Our model | GBM (risk-neutral) | GBM (real-world drift) | Option chain |")
    L.append("|---|---|---|---|---|")
    for r_ in rows:
        L.append(f"| {r_['event']} | {pct(r_['model'])} | {pct(r_['gbm_risk_neutral'])} "
                 f"| {pct(r_['gbm_real_world'])} | {pct(r_['chain'])} |")
    L.append("\n![Model vs. market](market_vs_model.png)\n")
    src = "option chain" if imp["source"] == "chain" else "single-implied-vol GBM"
    L.append("## What our weights would be if we agreed with the market\n")
    L.append(f"Each line moves one scenario's weight against the base case, holding the third fixed, "
             f"until our model's probability matches the market's ({src}). Targets use the "
             f"simulated average within each scenario.\n")
    L.append("| | Current | Matching market upside | Matching market downside |")
    L.append("|---|---|---|---|")
    L.append(f"| Bear weight | {weights['bear']:.0%} | {weights['bear']:.0%} (held) "
             f"| {imp['bear_weight_matching_downside']:.0%}{' (at limit)' if imp['bear_clamped'] else ''} |")
    L.append(f"| Bull weight | {weights['bull']:.0%} | {imp['bull_weight_matching_upside']:.0%}"
             f"{' (at limit)' if imp['bull_clamped'] else ''} | {weights['bull']:.0%} (held) |")
    L.append(f"| Target | ${imp['ev_current_weights']:.2f} | ${imp['ev_at_bull_weight']:.2f} "
             f"| ${imp['ev_at_bear_weight']:.2f} |")
    L.append(f"\nWorkbook three-scenario target for reference: ${point_ev:.2f}.\n")
    with open(path, "w") as f:
        f.write("\n".join(L))


if __name__ == "__main__":
    main()
