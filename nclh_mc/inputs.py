from dataclasses import dataclass, field
from pathlib import Path

from openpyxl import load_workbook

SCENARIOS = ("bear", "base", "bull")

COL_2026, COL_2027, COL_2028 = 3, 4, 5
COL_2025A = 4
SCENARIO_COL = {"bear": 3, "base": 4, "bull": 5}
SCENARIO_ROW_OFFSET = {"bear": 0, "base": 1, "bull": 2}


@dataclass
class ModelInputs:
    share_price: float
    shares_2028: float
    capacity_2026: float
    capacity_growth_2027: float
    capacity_growth_2028: float
    net_yield_2025: float
    net_yield_growth_2026: float
    ncc_2025: float
    ncc_growth_2026: float
    fuel_tonnes_2026: float
    fuel_use_change_2027: float
    fuel_use_change_2028: float
    fuel_price_2026: float
    hedge_share_2027: float
    hedge_price_2027: float
    hedge_share_2028: float
    hedge_price_2028: float
    net_debt_2025: float
    interest_2026: float
    interest_2027: float
    taxes_2026: float
    taxes_2027: float
    ats_2026: float
    newbuild_capex_2026: float
    newbuild_capex_2027: float
    other_capex_2026: float
    other_capex_2027: float
    asset_sales_2026: float
    asset_sales_2027: float
    peer_multiple: float
    exchange_prices: tuple
    exchange_shares: tuple
    drivers: dict = field(default_factory=dict)
    probabilities: dict = field(default_factory=dict)
    excel_targets: dict = field(default_factory=dict)


def _find_row(ws, label):
    for r in range(1, ws.max_row + 1):
        v = ws.cell(r, 1).value
        if isinstance(v, str) and v.strip() == label:
            return r
    raise KeyError(f"Label not found on sheet '{ws.title}': {label!r}")


def _val(ws, label, col):
    v = ws.cell(_find_row(ws, label), col).value
    if v is None:
        raise ValueError(
            f"Empty cell for {label!r} on '{ws.title}'. If it is a formula, "
            "open and save the workbook in Excel so its value is cached."
        )
    return float(v)


def _scenario_val(ws, label, scenario, col):
    r = _find_row(ws, label) + SCENARIO_ROW_OFFSET[scenario]
    tag = str(ws.cell(r, 2).value).strip().lower()
    if tag != scenario:
        raise ValueError(f"Expected '{scenario}' in column B, row {r}, found {tag!r}")
    return float(ws.cell(r, col).value or 0.0)


def load_inputs(path):
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"Workbook not found at {path}. Put the model in data/ or pass --workbook."
        )
    wb = load_workbook(path, data_only=True)
    inp, comps, val = wb["Inputs"], wb["Comps"], wb["Valuation"]

    drivers, probs, targets = {}, {}, {}
    target_row = _find_row(val, "12-month price target")
    for s in SCENARIOS:
        drivers[s] = {
            "yield_growth_2027": _scenario_val(inp, "Net yield growth (reported currency)", s, COL_2027),
            "yield_growth_2028": _scenario_val(inp, "Net yield growth (reported currency)", s, COL_2028),
            "ncc_growth_2027": _scenario_val(inp, "Adj. NCC ex-fuel per capacity day growth", s, COL_2027),
            "ncc_growth_2028": _scenario_val(inp, "Adj. NCC ex-fuel per capacity day growth", s, COL_2028),
            "fuel_price_2027": _scenario_val(inp, "Market fuel price before hedges ($/t)", s, COL_2027),
            "fuel_price_2028": _scenario_val(inp, "Market fuel price before hedges ($/t)", s, COL_2028),
            "ats_2027": _scenario_val(inp, "Change in advance ticket sales (+ = cash in)", s, COL_2027),
            "discount": _val(inp, "NCLH discount to RCL/CCL average forward EV/EBITDA", SCENARIO_COL[s]),
        }
        probs[s] = _val(inp, "Scenario probability", SCENARIO_COL[s])
        targets[s] = float(val.cell(target_row, SCENARIO_COL[s]).value)

    if abs(sum(probs.values()) - 1) > 1e-9:
        raise ValueError(f"Scenario probabilities sum to {sum(probs.values()):.4f}, not 1")

    return ModelInputs(
        share_price=_val(inp, "Share price", COL_2026),
        shares_2028=_val(inp, "Diluted shares before exchangeable-note dilution", COL_2028),
        capacity_2026=_val(inp, "Capacity days, 2026", COL_2026),
        capacity_growth_2027=_val(inp, "Capacity growth", COL_2027),
        capacity_growth_2028=_val(inp, "Capacity growth", COL_2028),
        net_yield_2025=_val(inp, "Net yield", COL_2025A),
        net_yield_growth_2026=_val(inp, "Net yield growth, 2026 (reported currency)", COL_2026),
        ncc_2025=_val(inp, "Adj. NCC ex-fuel per capacity day", COL_2025A),
        ncc_growth_2026=_val(inp, "Adj. NCC ex-fuel per capacity day growth, 2026", COL_2026),
        fuel_tonnes_2026=_val(inp, "Fuel consumption, 2026", COL_2026),
        fuel_use_change_2027=_val(inp, "Fuel use per capacity day, change", COL_2027),
        fuel_use_change_2028=_val(inp, "Fuel use per capacity day, change", COL_2028),
        fuel_price_2026=_val(inp, "Fuel price net of hedges, 2026", COL_2026),
        hedge_share_2027=_val(inp, "Share of fuel consumption hedged", COL_2027),
        hedge_price_2027=_val(inp, "Hedged fuel price", COL_2027),
        hedge_share_2028=_val(inp, "Share of fuel consumption hedged", COL_2028),
        hedge_price_2028=_val(inp, "Hedged fuel price", COL_2028),
        net_debt_2025=_val(inp, "Year-end net debt", COL_2025A),
        interest_2026=_val(inp, "Net interest expense (guidance)", COL_2026),
        interest_2027=_val(inp, "Net interest expense (guidance)", COL_2027),
        taxes_2026=_val(inp, "Taxes", COL_2026),
        taxes_2027=_val(inp, "Taxes", COL_2027),
        ats_2026=_val(inp, "Change in advance ticket sales, 2026 (+ = cash in)", COL_2026),
        newbuild_capex_2026=_val(inp, "Newbuild capex", COL_2026),
        newbuild_capex_2027=_val(inp, "Newbuild capex", COL_2027),
        other_capex_2026=_val(inp, "Other capex (maintenance, dry-dock, technology)", COL_2026),
        other_capex_2027=_val(inp, "Other capex (maintenance, dry-dock, technology)", COL_2027),
        asset_sales_2026=_val(inp, "Asset sale proceeds (Oceania Sirena; price not disclosed)", COL_2026),
        asset_sales_2027=_val(inp, "Asset sale proceeds (Oceania Sirena; price not disclosed)", COL_2027),
        peer_multiple=_val(comps, "RCL/CCL average, FY2 EV/EBITDA", 2),
        exchange_prices=(_val(inp, "Exchange price", 3), _val(inp, "Exchange price", 4)),
        exchange_shares=(_val(inp, "Shares underlying", 3), _val(inp, "Shares underlying", 4)),
        drivers=drivers,
        probabilities=probs,
        excel_targets=targets,
    )
