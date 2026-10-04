# NCLH Monte Carlo results

Share price $15.14. 100,000 draws, seed 42, downturn link rho = 0.0.

## Three-scenario target (workbook) vs. simulation

| | Bear | Base | Bull | Expected value |
|---|---|---|---|---|
| Probability | 25.0% | 30.0% | 45.0% | |
| Point target (workbook) | $0.00 | $17.67 | $30.30 | $18.94 |
| Simulated average | $2.24 | $17.88 | $30.04 | $19.47 |
| Share of draws valued at $0 | 64.8% | 5.8% | 0.5% | 18.1% |

## Distribution of outcomes

| Measure | Value |
|---|---|
| Expected value | $19.47 (+28.6%) |
| Standard deviation | $14.91 |
| Chance of any loss | 41.2% |
| Chance of losing more than half | 28.8% |
| Chance equity is valued at $0 by the model (not a bankruptcy probability) | 18.1% |
| Chance of gaining more than half | 43.2% |
| 5th / 25th / 50th / 75th / 95th percentile | $0.00 / $4.89 / $19.58 / $30.98 / $44.03 |

![Distribution](payoff_histogram.png)

## Robustness: how much the answer depends on the spreads

Spread scale multiplies every spread in config.toml. rho links yields, advance ticket sales and the multiple in a downturn.

| rho | Spread scale | Expected value | Gap vs. workbook target | Bear bucket average | Chance valued at $0 | Chance of loss |
|---|---|---|---|---|---|---|
| 0.0 | 0.5x | $19.09 | +0.15 | $0.62 | 19.3% | 35.0% |
| 0.0 | 1.0x | $19.47 | +0.53 | $2.24 | 18.1% | 41.2% |
| 0.0 | 1.5x | $20.20 | +1.26 | $4.01 | 21.5% | 44.9% |
| 0.0 | 2.0x | $21.27 | +2.34 | $5.80 | 25.5% | 46.7% |
| 0.5 | 0.5x | $19.16 | +0.22 | $0.90 | 18.5% | 36.2% |
| 0.5 | 1.0x | $19.78 | +0.84 | $2.92 | 18.9% | 42.8% |
| 0.5 | 1.5x | $20.93 | +2.00 | $5.10 | 23.4% | 45.7% |
| 0.5 | 2.0x | $22.55 | +3.61 | $7.30 | 27.8% | 47.1% |

## Convergence: run-to-run noise by number of draws

Each draw count was run with 20 different seeds.

| Draws | Expected value range | Chance-of-loss range |
|---|---|---|
| 1,000 | $18.81 to $20.19 | 38.3% to 42.8% |
| 10,000 | $19.10 to $19.67 | 40.1% to 42.1% |
| 100,000 | $19.34 to $19.53 | 41.1% to 41.7% |
| 1,000,000 | $19.38 to $19.44 | 41.3% to 41.5% |
