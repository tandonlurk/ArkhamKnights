# NCLH Monte Carlo results

> **Spreads in config.toml are still marked PLACEHOLDER.** Replace them with sourced values before quoting these numbers.

Share price $15.14. 100,000 draws, seed 42, downturn link rho = 0.0.

## Three-scenario target (workbook) vs. simulation

| | Bear | Base | Bull | Expected value |
|---|---|---|---|---|
| Probability | 25.0% | 30.0% | 45.0% | |
| Point target (workbook) | $0.00 | $17.67 | $30.30 | $18.94 |
| Simulated average | $0.43 | $17.69 | $30.22 | $19.04 |
| Share of draws valued at $0 | 81.4% | 0.0% | 0.0% | 20.3% |

## Distribution of outcomes

| Measure | Value |
|---|---|
| Expected value | $19.04 (+25.8%) |
| Standard deviation | $12.75 |
| Chance of any loss | 34.2% |
| Chance of losing more than half | 25.4% |
| Chance equity is valued at $0 by the model (not a bankruptcy probability) | 20.3% |
| Chance of gaining more than half | 46.5% |
| 5th / 25th / 50th / 75th / 95th percentile | $0.00 / $6.47 / $21.40 / $29.61 / $36.42 |

![Distribution](payoff_histogram.png)

## Robustness: how much the answer depends on the spreads

Spread scale multiplies every spread in config.toml. rho links yields, advance ticket sales and the multiple in a downturn.

| rho | Spread scale | Expected value | Gap vs. workbook target | Bear bucket average | Chance valued at $0 | Chance of loss |
|---|---|---|---|---|---|---|
| 0.0 | 0.5x | $18.98 | +0.04 | $0.03 | 24.0% | 29.4% |
| 0.0 | 1.0x | $19.04 | +0.10 | $0.43 | 20.3% | 34.2% |
| 0.0 | 1.5x | $19.07 | +0.14 | $1.05 | 18.3% | 37.1% |
| 0.0 | 2.0x | $19.04 | +0.11 | $1.76 | 17.9% | 40.2% |
| 0.5 | 0.5x | $19.02 | +0.08 | $0.14 | 22.4% | 31.7% |
| 0.5 | 1.0x | $19.22 | +0.28 | $0.92 | 18.5% | 36.1% |
| 0.5 | 1.5x | $19.46 | +0.52 | $1.95 | 17.6% | 39.8% |
| 0.5 | 2.0x | $19.72 | +0.78 | $3.07 | 18.5% | 42.5% |

## Convergence: run-to-run noise by number of draws

Each draw count was run with 20 different seeds.

| Draws | Expected value range | Chance-of-loss range |
|---|---|---|
| 1,000 | $18.57 to $19.59 | 31.0% to 36.7% |
| 10,000 | $18.75 to $19.28 | 33.2% to 35.2% |
| 100,000 | $18.93 to $19.09 | 34.1% to 34.6% |
| 1,000,000 | $18.97 to $19.02 | 34.2% to 34.4% |
