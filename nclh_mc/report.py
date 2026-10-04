import csv

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

COLORS = {"bear": "#B23A48", "base": "#8A8F98", "bull": "#2E6F95"}


def write_csv(rows, path):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def histogram(price, scen, names, share_price, point_ev, path):
    fig, ax = plt.subplots(figsize=(9, 5))
    top = np.ceil(np.percentile(price, 99.9))
    bins = np.arange(0, top + 1, 1.0)
    data = [price[scen == i] for i in range(len(names))]
    weights = [np.full(len(d), 100 / len(price)) for d in data]
    ax.hist(data, bins=bins, weights=weights, stacked=True,
            color=[COLORS.get(n, None) for n in names],
            label=[n.capitalize() for n in names], edgecolor="white", linewidth=0.4)

    ax.axvline(share_price, color="black", linewidth=1.2)
    ax.axvline(price.mean(), color="black", linewidth=1.2, linestyle="--")
    ymax = ax.get_ylim()[1]
    ax.text(share_price, ymax * 0.97, f" Share price ${share_price:.2f}", va="top", fontsize=9)
    ax.text(price.mean(), ymax * 0.90,
            f" Simulated expected value ${price.mean():.2f}\n (three-scenario target ${point_ev:.2f})",
            va="top", fontsize=9)
    p_zero = (price == 0).mean()
    ax.annotate(f"{p_zero:.0%} valued at $0\n(model floor, not\nbankruptcy odds)", xy=(0.5, min(ymax * 0.6, 100 * p_zero)),
                xytext=(3, ymax * 0.55), fontsize=9, arrowprops={"arrowstyle": "->", "lw": 0.8})

    ax.set_xlabel("12-month value per share ($)")
    ax.set_ylabel("Share of simulated outcomes (%)")
    ax.set_title("NCLH 12-month value: simulated distribution", loc="left", fontsize=12)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, loc="upper right", bbox_to_anchor=(1, 0.8))
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _pct(x):
    return f"{x:.1%}"


def markdown_summary(inp, cfg, point, point_ev, s, rob, conv, path):
    L = []
    L.append("# NCLH Monte Carlo results\n")
    L.append(f"Share price ${inp.share_price:.2f}. {cfg['draws']:,} draws, seed {cfg['seed']}, "
             f"downturn link rho = {cfg['downturn']['rho']}.\n")

    L.append("## Three-scenario target (workbook) vs. simulation\n")
    L.append("| | Bear | Base | Bull | Expected value |")
    L.append("|---|---|---|---|---|")
    L.append(f"| Probability | {_pct(inp.probabilities['bear'])} | {_pct(inp.probabilities['base'])} "
             f"| {_pct(inp.probabilities['bull'])} | |")
    L.append(f"| Point target (workbook) | ${point['bear']:.2f} | ${point['base']:.2f} "
             f"| ${point['bull']:.2f} | ${point_ev:.2f} |")
    b = s["by_scenario"]
    L.append(f"| Simulated average | ${b['bear']['mean']:.2f} | ${b['base']['mean']:.2f} "
             f"| ${b['bull']['mean']:.2f} | ${s['expected_price']:.2f} |")
    L.append(f"| Share of draws valued at $0 | {_pct(b['bear']['p_zero'])} | {_pct(b['base']['p_zero'])} "
             f"| {_pct(b['bull']['p_zero'])} | {_pct(s['p_zero'])} |\n")

    L.append("## Distribution of outcomes\n")
    L.append("| Measure | Value |")
    L.append("|---|---|")
    L.append(f"| Expected value | ${s['expected_price']:.2f} ({s['expected_return']:+.1%}) |")
    L.append(f"| Standard deviation | ${s['std']:.2f} |")
    L.append(f"| Chance of any loss | {_pct(s['p_loss'])} |")
    L.append(f"| Chance of losing more than half | {_pct(s['p_loss_over_half'])} |")
    L.append(f"| Chance equity is valued at $0 by the model (not a bankruptcy probability) | {_pct(s['p_zero'])} |")
    L.append(f"| Chance of gaining more than half | {_pct(s['p_gain_over_half'])} |")
    pc = s["percentiles"]
    L.append(f"| 5th / 25th / 50th / 75th / 95th percentile | ${pc[5]:.2f} / ${pc[25]:.2f} / "
             f"${pc[50]:.2f} / ${pc[75]:.2f} / ${pc[95]:.2f} |\n")
    L.append("![Distribution](payoff_histogram.png)\n")

    L.append("## Robustness: how much the answer depends on the spreads\n")
    L.append("Spread scale multiplies every spread in config.toml. rho links yields, advance ticket "
             "sales and the multiple in a downturn.\n")
    L.append("| rho | Spread scale | Expected value | Gap vs. workbook target | Bear bucket average "
             "| Chance valued at $0 | Chance of loss |")
    L.append("|---|---|---|---|---|---|---|")
    for r in rob:
        L.append(f"| {r['rho']} | {r['spread_scale']}x | ${r['expected_price']:.2f} "
                 f"| {r['gap_vs_point_target']:+.2f} | ${r['bear_bucket_mean']:.2f} "
                 f"| {_pct(r['p_zero'])} | {_pct(r['p_loss'])} |")
    L.append("")

    L.append("## Convergence: run-to-run noise by number of draws\n")
    L.append(f"Each draw count was run with {cfg['convergence']['seeds']} different seeds.\n")
    L.append("| Draws | Expected value range | Chance-of-loss range |")
    L.append("|---|---|---|")
    for c in conv:
        L.append(f"| {c['draws']:,} | ${c['expected_price_min']:.2f} to ${c['expected_price_max']:.2f} "
                 f"| {_pct(c['p_loss_min'])} to {_pct(c['p_loss_max'])} |")
    L.append("")
    with open(path, "w") as f:
        f.write("\n".join(L))
