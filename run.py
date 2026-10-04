import argparse
import json
import tomllib
from pathlib import Path

from nclh_mc.inputs import load_inputs
from nclh_mc.model import point_expected_value, point_targets
from nclh_mc.report import histogram, markdown_summary, write_csv
from nclh_mc.simulate import convergence, robustness, simulate, summarize

TOLERANCE = 0.01  # $/share


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="config.toml")
    ap.add_argument("--workbook", help="override the workbook path in config")
    ap.add_argument("--draws", type=int)
    ap.add_argument("--seed", type=int)
    ap.add_argument("--rho", type=float, help="downturn link, 0 to 1")
    ap.add_argument("--out", default="results")
    ap.add_argument("--skip-extras", action="store_true", help="skip robustness and convergence runs")
    args = ap.parse_args()

    with open(args.config, "rb") as f:
        cfg = tomllib.load(f)
    for key in ("draws", "seed"):
        if getattr(args, key) is not None:
            cfg[key] = getattr(args, key)
    if args.rho is not None:
        cfg["downturn"]["rho"] = args.rho

    inp = load_inputs(args.workbook or cfg["workbook"])

    point = point_targets(inp)
    for s, target in point.items():
        diff = abs(target - inp.excel_targets[s])
        if diff > TOLERANCE:
            raise SystemExit(
                f"{s} target ${target:.4f} differs from the workbook's ${inp.excel_targets[s]:.4f}. "
                "The model's logic has changed; update nclh_mc/model.py before trusting results."
            )
    point_ev = point_expected_value(inp)
    print("Validation passed: Python reproduces the workbook's targets "
          + ", ".join(f"{s} ${v:.2f}" for s, v in point.items()) + f" (EV ${point_ev:.2f})")

    price, scen, names = simulate(inp, cfg)
    s = summarize(price, scen, names, inp.share_price)
    print(f"Simulated expected value ${s['expected_price']:.2f} "
          f"({s['expected_return']:+.1%}) vs. workbook ${point_ev:.2f}")
    print(f"Chance of loss {s['p_loss']:.1%} | lose >50% {s['p_loss_over_half']:.1%} | "
          f"valued at $0 {s['p_zero']:.1%} | gain >50% {s['p_gain_over_half']:.1%}")

    out = Path(args.out)
    out.mkdir(exist_ok=True)
    histogram(price, scen, names, inp.share_price, point_ev, out / "payoff_histogram.png")
    with open(out / "summary.json", "w") as f:
        json.dump({"point_targets": point, "point_expected_value": point_ev, "simulation": s}, f, indent=2)

    rob, conv = [], []
    if not args.skip_extras:
        rob = robustness(inp, cfg)
        conv = convergence(inp, cfg)
        write_csv(rob, out / "robustness.csv")
        write_csv(conv, out / "convergence.csv")
        markdown_summary(inp, cfg, point, point_ev, s, rob, conv, out / "summary.md")
    print(f"Results written to {out}/")


if __name__ == "__main__":
    main()
