import copy
import tomllib
from pathlib import Path

import numpy as np
import pytest

from nclh_mc.inputs import load_inputs
from nclh_mc.model import point_expected_value, point_targets
from nclh_mc.simulate import draw_shocks, simulate

ROOT = Path(__file__).resolve().parents[1]
with open(ROOT / "config.toml", "rb") as f:
    CFG = tomllib.load(f)
WORKBOOK = ROOT / CFG["workbook"]
pytestmark = pytest.mark.skipif(not WORKBOOK.exists(), reason="workbook not in data/")


@pytest.fixture(scope="module")
def inp():
    return load_inputs(WORKBOOK)


def test_replica_matches_workbook_targets(inp):
    for s, target in point_targets(inp).items():
        assert target == pytest.approx(inp.excel_targets[s], abs=0.005)


def test_point_expected_value_is_sumproduct(inp):
    t = point_targets(inp)
    assert point_expected_value(inp) == pytest.approx(sum(inp.probabilities[s] * t[s] for s in t))


def test_zero_spreads_reproduce_point_targets(inp):
    cfg = copy.deepcopy(CFG)
    cfg["spreads"] = {k: 0.0 for k in cfg["spreads"]}
    price, scen, names = simulate(inp, cfg, draws=20000)
    point = point_targets(inp)
    for i, name in enumerate(names):
        assert np.allclose(price[scen == i], point[name])


def test_scenario_frequencies_match_probabilities(inp):
    _, scen, names = simulate(inp, CFG, draws=200000)
    for i, name in enumerate(names):
        assert (scen == i).mean() == pytest.approx(inp.probabilities[name], abs=0.005)


def test_prices_never_negative(inp):
    cfg = copy.deepcopy(CFG)
    price, _, _ = simulate(inp, cfg, draws=50000, spread_scale=3.0)
    assert (price >= 0).all()


def test_downturn_shocks_keep_unit_variance_and_link():
    rng = np.random.default_rng(0)
    direction = {"yield_growth_2027": -1, "discount": 1}
    z = draw_shocks(rng, 400000, 0.5, direction)
    assert z["yield_growth_2027"].std() == pytest.approx(1, abs=0.01)
    assert z["discount"].std() == pytest.approx(1, abs=0.01)
    assert np.corrcoef(z["yield_growth_2027"], z["discount"])[0, 1] == pytest.approx(-0.5, abs=0.01)
    assert abs(np.corrcoef(z["yield_growth_2027"], z["fuel_price"])[0, 1]) < 0.01
