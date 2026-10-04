"""Vectorized replica of the workbook's valuation path.

The 12-month target in the workbook depends only on 2028E adj. EBITDA,
year-end 2027E net debt, the target multiple and 2028E diluted shares
(Valuation tab, rows 18-28). This module rebuilds exactly that chain from the
Model tab's formulas, so every driver can be passed as a numpy array and one
call prices every simulated draw at once.

    Adj. EBITDA = net yield x capacity days - NCC ex-fuel x capacity days - fuel
    Net debt(t) = net debt(t-1) - free cash flow(t)
    Equity      = target multiple x 2028E EBITDA - 2027E net debt
    Target      = equity / diluted shares incl. exchangeable notes, floored at $0
"""
import numpy as np


def project(inp, yield_growth_2027, yield_growth_2028, ncc_growth_2027, ncc_growth_2028,
            fuel_price_2027, fuel_price_2028, ats_2027, discount, peer_multiple=None):
    """Return a dict of arrays: ebitda_2028, net_debt_2027, multiple, equity, price."""
    if peer_multiple is None:
        peer_multiple = inp.peer_multiple

    # Capacity (shared across scenarios)
    cap26 = inp.capacity_2026
    cap27 = cap26 * (1 + inp.capacity_growth_2027)
    cap28 = cap27 * (1 + inp.capacity_growth_2028)

    # Unit revenue and unit cost
    y26 = inp.net_yield_2025 * (1 + inp.net_yield_growth_2026)
    y27 = y26 * (1 + yield_growth_2027)
    y28 = y27 * (1 + yield_growth_2028)
    n26 = inp.ncc_2025 * (1 + inp.ncc_growth_2026)
    n27 = n26 * (1 + ncc_growth_2027)
    n28 = n27 * (1 + ncc_growth_2028)

    # Fuel: tonnes scale with capacity; price is the hedged blend
    t26 = inp.fuel_tonnes_2026
    t27 = t26 * (cap27 / cap26) * (1 + inp.fuel_use_change_2027)
    t28 = t27 * (cap28 / cap27) * (1 + inp.fuel_use_change_2028)
    p27 = inp.hedge_share_2027 * inp.hedge_price_2027 + (1 - inp.hedge_share_2027) * fuel_price_2027
    p28 = inp.hedge_share_2028 * inp.hedge_price_2028 + (1 - inp.hedge_share_2028) * fuel_price_2028

    ebitda26 = y26 * cap26 - n26 * cap26 - t26 * inp.fuel_price_2026 / 1000
    ebitda27 = y27 * cap27 - n27 * cap27 - t27 * p27 / 1000
    ebitda28 = y28 * cap28 - n28 * cap28 - t28 * p28 / 1000

    # Free cash flow and net debt (2027 interest is company guidance in every scenario)
    fcf26 = (ebitda26 - inp.interest_2026 - inp.taxes_2026 + inp.ats_2026
             - inp.newbuild_capex_2026 - inp.other_capex_2026 + inp.asset_sales_2026)
    fcf27 = (ebitda27 - inp.interest_2027 - inp.taxes_2027 + ats_2027
             - inp.newbuild_capex_2027 - inp.other_capex_2027 + inp.asset_sales_2027)
    nd26 = inp.net_debt_2025 - fcf26
    nd27 = nd26 - fcf27

    # Valuation
    multiple = peer_multiple * (1 - discount)
    equity = multiple * ebitda28 - nd27
    shares = inp.shares_2028
    price_pre = np.maximum(0.0, equity / shares)

    # Exchangeable notes: treasury-style dilution when the price is above the exchange price
    dilution = np.zeros_like(np.asarray(price_pre, dtype=float))
    safe_price = np.where(price_pre > 0, price_pre, 1.0)
    for x_price, x_shares in zip(inp.exchange_prices, inp.exchange_shares):
        dilution = dilution + np.where(price_pre > x_price,
                                       x_shares * (price_pre - x_price) / safe_price, 0.0)
    price = np.maximum(0.0, equity / (shares + dilution))

    return {"ebitda_2028": ebitda28, "net_debt_2027": nd27, "multiple": multiple,
            "equity": equity, "price": price}


def point_targets(inp):
    """Price each scenario at its point assumptions (what the workbook does)."""
    return {s: float(project(inp, **d)["price"]) for s, d in inp.drivers.items()}


def point_expected_value(inp):
    t = point_targets(inp)
    return sum(inp.probabilities[s] * t[s] for s in t)
