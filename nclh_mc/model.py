import numpy as np


def project(inp, yield_growth_2027, yield_growth_2028, ncc_growth_2027, ncc_growth_2028,
            fuel_price_2027, fuel_price_2028, ats_2027, discount, peer_multiple=None):
    if peer_multiple is None:
        peer_multiple = inp.peer_multiple

    cap26 = inp.capacity_2026
    cap27 = cap26 * (1 + inp.capacity_growth_2027)
    cap28 = cap27 * (1 + inp.capacity_growth_2028)

    y26 = inp.net_yield_2025 * (1 + inp.net_yield_growth_2026)
    y27 = y26 * (1 + yield_growth_2027)
    y28 = y27 * (1 + yield_growth_2028)
    n26 = inp.ncc_2025 * (1 + inp.ncc_growth_2026)
    n27 = n26 * (1 + ncc_growth_2027)
    n28 = n27 * (1 + ncc_growth_2028)

    t26 = inp.fuel_tonnes_2026
    t27 = t26 * (cap27 / cap26) * (1 + inp.fuel_use_change_2027)
    t28 = t27 * (cap28 / cap27) * (1 + inp.fuel_use_change_2028)
    # hedged blend
    p27 = inp.hedge_share_2027 * inp.hedge_price_2027 + (1 - inp.hedge_share_2027) * fuel_price_2027
    p28 = inp.hedge_share_2028 * inp.hedge_price_2028 + (1 - inp.hedge_share_2028) * fuel_price_2028

    ebitda26 = y26 * cap26 - n26 * cap26 - t26 * inp.fuel_price_2026 / 1000
    ebitda27 = y27 * cap27 - n27 * cap27 - t27 * p27 / 1000
    ebitda28 = y28 * cap28 - n28 * cap28 - t28 * p28 / 1000

    fcf26 = (ebitda26 - inp.interest_2026 - inp.taxes_2026 + inp.ats_2026
             - inp.newbuild_capex_2026 - inp.other_capex_2026 + inp.asset_sales_2026)
    fcf27 = (ebitda27 - inp.interest_2027 - inp.taxes_2027 + ats_2027
             - inp.newbuild_capex_2027 - inp.other_capex_2027 + inp.asset_sales_2027)
    nd26 = inp.net_debt_2025 - fcf26
    nd27 = nd26 - fcf27

    # EV/EBITDA
    multiple = peer_multiple * (1 - discount)
    equity = multiple * ebitda28 - nd27
    shares = inp.shares_2028
    price_pre = np.maximum(0.0, equity / shares)

    # treasury method
    dilution = np.zeros_like(np.asarray(price_pre, dtype=float))
    safe_price = np.where(price_pre > 0, price_pre, 1.0)
    for x_price, x_shares in zip(inp.exchange_prices, inp.exchange_shares):
        dilution = dilution + np.where(price_pre > x_price,
                                       x_shares * (price_pre - x_price) / safe_price, 0.0)
    price = np.maximum(0.0, equity / (shares + dilution))

    return {"ebitda_2028": ebitda28, "net_debt_2027": nd27, "multiple": multiple,
            "equity": equity, "price": price}


def point_targets(inp):
    return {s: float(project(inp, **d)["price"]) for s, d in inp.drivers.items()}


def point_expected_value(inp):
    t = point_targets(inp)
    return sum(inp.probabilities[s] * t[s] for s in t)
