import csv
import datetime as dt
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from nclh_mc.market import bs_price

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "format_chain.py"
S, R, EXPIRY, PDATE = 15.14, 0.0446, "2027-09-17", "2026-10-02"
T = (dt.date.fromisoformat(EXPIRY) - dt.date.fromisoformat(PDATE)).days / 365.25
STRIKES = [2.5, 5, 7.5, 10, 12.5, 15, 17.5, 20, 22.5, 25, 27.5, 30, 32.5, 35, 40]


def write_raw(path, bump=None):
    vol = 0.55 + 0.15 * np.log(S / np.array(STRIKES))
    calls = bs_price(S, STRIKES, T, R, vol, "call")
    puts = bs_price(S, STRIKES, T, R, vol, "put")
    with open(path, "w", newline="") as f:
        f.write("# test quotes\n")
        w = csv.writer(f)
        w.writerow(["strike", "call_bid", "call_ask", "put_bid", "put_ask", "call_oi", "put_oi"])
        for k, c, p in zip(STRIKES, calls, puts):
            cb, ca = max(c - 0.05, 0.01), c + 0.05
            pb, pa = max(p - 0.05, 0.01), p + 0.05
            if bump and k == bump[0]:
                ca += bump[1]
                cb += bump[1]
            w.writerow([k, f"{cb:.2f}", f"{ca:.2f}", f"{pb:.2f}", f"{pa:.2f}", 100, 100])


def run(raw, out, spot=S):
    return subprocess.run([sys.executable, str(SCRIPT), str(raw), "--spot", str(spot), "--expiry", EXPIRY,
                           "--rate", str(R), "--pricing-date", PDATE, "--out", str(out)],
                          capture_output=True, text=True, cwd=ROOT)


def test_clean_quotes_pass_and_recover_vol(tmp_path):
    raw, out = tmp_path / "raw.csv", tmp_path / "chain.csv"
    write_raw(raw)
    res = run(raw, out)
    assert res.returncode == 0, res.stdout + res.stderr
    assert "No-arbitrage checks passed" in res.stdout
    line = next(ln for ln in res.stdout.splitlines() if "At-the-money implied vol" in ln)
    iv = float(line.split(":")[1].split("%")[0]) / 100
    assert iv == pytest.approx(0.55 + 0.15 * np.log(S / 15), abs=0.02)
    with open(out) as f:
        assert next(csv.reader(f)) == ["strike", "call_mid", "put_mid"]


def test_stale_quote_is_flagged(tmp_path):
    raw, out = tmp_path / "raw.csv", tmp_path / "chain.csv"
    write_raw(raw, bump=(32.5, 1.0))
    res = run(raw, out)
    assert res.returncode == 2
    assert "No-arbitrage violations" in res.stdout


def test_wrong_day_spot_is_flagged(tmp_path):
    raw, out = tmp_path / "raw.csv", tmp_path / "chain.csv"
    write_raw(raw)
    res = run(raw, out, spot=16.50)
    assert res.returncode == 2
    assert "more than 2% off" in res.stdout
