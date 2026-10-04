"""Run with:  pytest -q"""
import numpy as np
import pytest

from nclh_mc.market import (
    bs_price, chain_prob_above, gbm_prob_above, implied_vol, implied_weight,
    interp_prob_above, synthetic_chain,
)

S, T, R = 15.14, 1.0, 0.04


def test_implied_vol_round_trip():
    for kind in ("call", "put"):
        for k in (8.0, 15.0, 25.0):
            price = float(bs_price(S, k, T, R, 0.55, kind))
            assert implied_vol(price, S, k, T, R, kind) == pytest.approx(0.55, abs=1e-4)


def test_gbm_probability_limits_and_median():
    assert float(gbm_prob_above(S, 0.01, T, R, 0.6)) > 0.999
    assert float(gbm_prob_above(S, 1000, T, R, 0.6)) < 0.001
    median = S * np.exp((R - 0.5 * 0.6 ** 2) * T)
    assert float(gbm_prob_above(S, median, T, R, 0.6)) == pytest.approx(0.5, abs=1e-9)


def test_chain_recovers_flat_vol_probabilities():
    strikes = np.arange(1.0, 61.0, 1.0)
    k, c, p = synthetic_chain(S, T, R, 0.55, 0.0, strikes)
    mids, probs = chain_prob_above(k, c, p, S, T, R)
    for level in (7.57, 15.14, 22.71, 30.30):
        assert interp_prob_above(mids, probs, level) == pytest.approx(
            float(gbm_prob_above(S, level, T, R, 0.55)), abs=0.02)


def test_puts_converted_by_parity_match_calls():
    strikes = np.arange(1.0, 61.0, 1.0)
    k, c, p = synthetic_chain(S, T, R, 0.55, 0.2, strikes)
    calls_only = chain_prob_above(k, c, np.full_like(p, np.nan), S, T, R)[1]
    c_masked = np.where(k < S, np.nan, c)
    with_puts = chain_prob_above(k, c_masked, p, S, T, R)[1]
    assert np.allclose(calls_only, with_puts, atol=0.02)


def test_chain_probabilities_are_monotone_and_bounded():
    k, c, p = synthetic_chain(S, T, R, 0.6, 0.2, [1, 2.5, 5, 7.5, 10, 12.5, 15, 17.5, 20, 25, 30, 40])
    c = c + np.random.default_rng(0).normal(0, 0.03, len(c))  # quote noise
    _, probs = chain_prob_above(k, c, p, S, T, R)
    assert (probs >= 0).all() and (probs <= 1).all()
    assert (np.diff(probs) <= 1e-12).all()


def test_outside_strike_range_is_nan():
    mids, probs = np.array([5.0, 10.0, 20.0]), np.array([0.9, 0.6, 0.2])
    assert np.isnan(interp_prob_above(mids, probs, 2.0))
    assert np.isnan(interp_prob_above(mids, probs, 25.0))


def test_implied_weight_recovers_current_weights():
    weights = {"bear": 0.25, "base": 0.30, "bull": 0.45}
    cond = {"bear": 0.01, "base": 0.10, "bull": 0.85}
    target = sum(weights[s] * cond[s] for s in weights)
    w, clamped = implied_weight(cond, weights, target, "bull", "base", "bear")
    assert w == pytest.approx(0.45) and not clamped


def test_implied_weight_clamps_when_unreachable():
    weights = {"bear": 0.25, "base": 0.30, "bull": 0.45}
    cond = {"bear": 0.0, "base": 0.10, "bull": 0.85}
    w, clamped = implied_weight(cond, weights, 0.99, "bull", "base", "bear")
    assert w == pytest.approx(0.75) and clamped
