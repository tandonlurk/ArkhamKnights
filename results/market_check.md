# Market cross-check: options-implied probabilities vs. our model

> **Warning:** market_config.toml still has PLACEHOLDER values (implied vol and/or rate).

> **Warning:** config.toml spreads are still PLACEHOLDERs, so the model side is illustrative.

> **Warning:** The option chain is the SYNTHETIC EXAMPLE file. Chain results are not real market data.

Share price $15.14. Single implied vol 60%, risk-free rate 4.0%, real-world drift 10%, horizon 1 year.
 Option chain: `data/option_chain_EXAMPLE.csv`, 0.96 years to expiry, at-the-money implied vol from the chain 58%.


## Probabilities

GBM = lognormal from the single implied vol. Chain = risk-neutral probabilities from option prices across strikes (includes skew). Market columns are prices, not forecasts; the real-world GBM column shows how little a higher expected return changes them.

| Event | Our model | GBM (risk-neutral) | GBM (real-world drift) | Option chain |
|---|---|---|---|---|
| Any loss | 34.2% | 59.2% | 55.3% | 50.8% |
| Lose more than half | 25.4% | 17.8% | 15.3% | 18.7% |
| Gain more than half | 46.5% | 18.2% | 20.9% | 21.0% |
| Above base target ($17.67) | 59.7% | 31.2% | 34.8% | 38.5% |
| Above bull target ($30.30) | 22.5% | 8.2% | 9.9% | 6.1% |

![Model vs. market](market_vs_model.png)

## What our weights would be if we agreed with the market

Each line moves one scenario's weight against the base case, holding the third fixed, until our model's probability matches the market's (option chain). Targets use the simulated average within each scenario.

| | Current | Matching market upside | Matching market downside |
|---|---|---|---|
| Bear weight | 25% | 25% (held) | 18% |
| Bull weight | 45% | 12% | 45% (held) |
| Target | $19.01 | $14.90 | $20.19 |

Workbook three-scenario target for reference: $18.94.

## How to read this

The gap between our column and the market columns is our variant view. A long thesis needs one, but each gap should be backed by a specific reason the market is mispricing NCLH. Where we cannot explain a gap, the matching weight above is what our target would be without that conviction.
