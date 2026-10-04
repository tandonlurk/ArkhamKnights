import numpy as np

from .model import point_expected_value, project

SHOCKED = ["yield_growth_2027", "yield_growth_2028", "ncc_growth_2027", "ncc_growth_2028",
           "fuel_price", "ats_2027", "discount", "peer_multiple"]


def draw_shocks(rng, n, rho, direction):
    common = rng.standard_normal(n)  # one-factor
    shocks = {}
    for name in SHOCKED:
        load = direction.get(name, 0) * np.sqrt(rho)
        shocks[name] = load * common + np.sqrt(1 - load ** 2) * rng.standard_normal(n)
    return shocks


def simulate(inp, cfg, draws=None, seed=None, spread_scale=1.0, rho=None):
    draws = int(draws or cfg["draws"])
    seed = cfg["seed"] if seed is None else seed
    rho = cfg["downturn"]["rho"] if rho is None else rho
    rng = np.random.default_rng(seed)

    names = list(inp.drivers)
    probs = np.array([inp.probabilities[s] for s in names])
    scen = rng.choice(len(names), size=draws, p=probs)

    def center(key):
        return np.array([inp.drivers[s][key] for s in names])[scen]

    sd = {k: v * spread_scale for k, v in cfg["spreads"].items()}
    z = draw_shocks(rng, draws, rho, cfg["downturn"]["direction"])
    b = cfg["bounds"]

    drivers = {
        "yield_growth_2027": center("yield_growth_2027") + sd["yield_growth_2027"] * z["yield_growth_2027"],
        "yield_growth_2028": center("yield_growth_2028") + sd["yield_growth_2028"] * z["yield_growth_2028"],
        "ncc_growth_2027": center("ncc_growth_2027") + sd["ncc_growth_2027"] * z["ncc_growth_2027"],
        "ncc_growth_2028": center("ncc_growth_2028") + sd["ncc_growth_2028"] * z["ncc_growth_2028"],
        "fuel_price_2027": np.maximum(center("fuel_price_2027") + sd["fuel_price"] * z["fuel_price"], b["fuel_price_min"]),
        "fuel_price_2028": np.maximum(center("fuel_price_2028") + sd["fuel_price"] * z["fuel_price"], b["fuel_price_min"]),
        "ats_2027": center("ats_2027") + sd["ats_2027"] * z["ats_2027"],
        "discount": np.clip(center("discount") + sd["discount"] * z["discount"],
                            b["discount_min"], b["discount_max"]),
        "peer_multiple": np.maximum(inp.peer_multiple + sd["peer_multiple"] * z["peer_multiple"],
                                    b["peer_multiple_min"]),
    }
    return project(inp, **drivers)["price"], scen, names


def summarize(price, scen, names, share_price):
    ret = price / share_price - 1
    out = {
        "expected_price": float(price.mean()),
        "expected_return": float(ret.mean()),
        "std": float(price.std()),
        "p_zero": float((price == 0).mean()),
        "p_loss": float((price < share_price).mean()),
        "p_loss_over_half": float((ret < -0.5).mean()),
        "p_gain_over_half": float((ret > 0.5).mean()),
        "percentiles": {p: float(np.percentile(price, p)) for p in (5, 25, 50, 75, 95)},
        "by_scenario": {},
    }
    for i, name in enumerate(names):
        mask = scen == i
        out["by_scenario"][name] = {
            "share_of_draws": float(mask.mean()),
            "mean": float(price[mask].mean()),
            "p_zero": float((price[mask] == 0).mean()),
        }
    return out


def robustness(inp, cfg):
    point_ev = point_expected_value(inp)
    rows = []
    for rho in cfg["robustness"]["rhos"]:
        for scale in cfg["robustness"]["spread_scales"]:
            price, scen, names = simulate(inp, cfg, draws=cfg["robustness"]["draws"],
                                          spread_scale=scale, rho=rho)
            s = summarize(price, scen, names, inp.share_price)
            rows.append({
                "rho": rho,
                "spread_scale": scale,
                "expected_price": s["expected_price"],
                "gap_vs_point_target": s["expected_price"] - point_ev,
                "bear_bucket_mean": s["by_scenario"]["bear"]["mean"],
                "p_zero": s["p_zero"],
                "p_loss": s["p_loss"],
                "p_loss_over_half": s["p_loss_over_half"],
            })
    return rows


def convergence(inp, cfg):
    rows = []
    for n in cfg["convergence"]["draw_counts"]:
        means, losses = [], []
        for seed in range(cfg["convergence"]["seeds"]):
            price, _, _ = simulate(inp, cfg, draws=n, seed=seed)
            means.append(price.mean())
            losses.append((price < inp.share_price).mean())
        rows.append({
            "draws": n,
            "expected_price_min": float(np.min(means)),
            "expected_price_max": float(np.max(means)),
            "expected_price_sd": float(np.std(means)),
            "p_loss_min": float(np.min(losses)),
            "p_loss_max": float(np.max(losses)),
        })
    return rows
