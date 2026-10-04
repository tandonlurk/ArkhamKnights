import csv
import math

import numpy as np

_SQRT2 = math.sqrt(2.0)
_erf = np.vectorize(math.erf)


def norm_cdf(x):
    return 0.5 * (1.0 + _erf(np.asarray(x, dtype=float) / _SQRT2))


def bs_price(S, K, T, r, sigma, kind="call", q=0.0):
    K = np.asarray(K, dtype=float)
    sigma = np.asarray(sigma, dtype=float)
    d1 = (np.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    if kind == "call":
        return S * math.exp(-q * T) * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)
    return K * math.exp(-r * T) * norm_cdf(-d2) - S * math.exp(-q * T) * norm_cdf(-d1)


def implied_vol(price, S, K, T, r, kind="call", q=0.0, lo=1e-4, hi=5.0):
    f_lo = float(bs_price(S, K, T, r, lo, kind, q)) - price
    f_hi = float(bs_price(S, K, T, r, hi, kind, q)) - price
    if f_lo * f_hi > 0:
        return float("nan")
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        f_mid = float(bs_price(S, K, T, r, mid, kind, q)) - price
        if f_lo * f_mid <= 0:
            hi = mid
        else:
            lo, f_lo = mid, f_mid
    return 0.5 * (lo + hi)


def gbm_prob_above(S, K, T, drift, sigma):
    K = np.asarray(K, dtype=float)
    d2 = (np.log(S / K) + (drift - 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    return norm_cdf(d2)


def load_chain(path):
    strikes, calls, puts = [], [], []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            if not row.get("strike"):
                continue
            strikes.append(float(row["strike"]))
            calls.append(float(row["call_mid"]) if row.get("call_mid") else np.nan)
            puts.append(float(row["put_mid"]) if row.get("put_mid") else np.nan)
    order = np.argsort(strikes)
    return np.array(strikes)[order], np.array(calls)[order], np.array(puts)[order]


# Breeden-Litzenberger
def chain_prob_above(strikes, call_mid, put_mid, S, T, r, q=0.0):
    # put-call parity
    parity = put_mid + S * math.exp(-q * T) - strikes * math.exp(-r * T)
    use_put = (strikes < S) & ~np.isnan(put_mid)
    call_equiv = np.where(use_put, parity, call_mid)
    if np.isnan(call_equiv).any():
        call_equiv = np.where(np.isnan(call_equiv), parity, call_equiv)
    keep = ~np.isnan(call_equiv)
    k, c = strikes[keep], call_equiv[keep]
    if len(k) < 3:
        raise ValueError("Need at least three strikes with usable prices.")
    mids = 0.5 * (k[1:] + k[:-1])
    probs = -math.exp(r * T) * np.diff(c) / np.diff(k)
    probs = np.minimum.accumulate(np.clip(probs, 0.0, 1.0))
    return mids, probs


def interp_prob_above(mids, probs, K):
    if K < mids[0] or K > mids[-1]:
        return float("nan")
    return float(np.interp(K, mids, probs))


def synthetic_chain(S, T, r, base_vol, skew, strikes):
    vol = base_vol + skew * np.log(S / np.asarray(strikes, dtype=float))
    calls = np.round(bs_price(S, strikes, T, r, vol, "call"), 2)
    puts = np.round(bs_price(S, strikes, T, r, vol, "put"), 2)
    return np.asarray(strikes, dtype=float), calls, puts


def thresholds(share_price, point_targets):
    return [
        ("Any loss", share_price, "below"),
        ("Lose more than half", 0.5 * share_price, "below"),
        ("Gain more than half", 1.5 * share_price, "above"),
        (f"Above base target (${point_targets['base']:.2f})", point_targets["base"], "above"),
        (f"Above bull target (${point_targets['bull']:.2f})", point_targets["bull"], "above"),
    ]


def model_prob(price, level, side):
    return float((price < level).mean() if side == "below" else (price > level).mean())


def conditional_probs(price, scen, names, level, side):
    return {n: model_prob(price[scen == i], level, side) for i, n in enumerate(names)}


def implied_weight(cond, weights, target, vary, against, hold):
    pool = weights[vary] + weights[against]
    denom = cond[vary] - cond[against]
    if abs(denom) < 1e-12 or math.isnan(target):
        return float("nan"), False
    w = (target - weights[hold] * cond[hold] - pool * cond[against]) / denom
    clamped = w < 0 or w > pool
    return float(min(max(w, 0.0), pool)), clamped


def expected_value(weights, scenario_means):
    return sum(weights[s] * scenario_means[s] for s in weights)
