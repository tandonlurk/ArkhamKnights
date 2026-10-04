# Market cross-check: options-implied probabilities vs. our model

Share price $15.14. Single implied vol 54%, risk-free rate 4.5%, real-world drift 10%, horizon 1 year.
 Option chain: `data/nclh_chain_2027-09-17.csv`, 0.96 years to expiry, at-the-money implied vol from the chain 54%.


## Probabilities

GBM: lognormal, single implied vol. Chain: risk-neutral, Breeden-Litzenberger across strikes.

| Event | Our model | GBM (risk-neutral) | GBM (real-world drift) | Option chain |
|---|---|---|---|---|
| Any loss | 41.2% | 57.5% | 53.4% | 54.5% |
| Lose more than half | 28.8% | 13.8% | 11.7% | 11.7% |
| Gain more than half | 43.2% | 17.4% | 20.2% | 20.1% |
| Above base target ($17.67) | 54.0% | 31.8% | 35.5% | 33.3% |
| Above bull target ($30.30) | 26.4% | 7.1% | 8.6% | n/a |

![Model vs. market](market_vs_model.png)

## What our weights would be if we agreed with the market

Each line moves one scenario's weight against the base case, holding the third fixed, until our model's probability matches the market's (option chain). Targets use the simulated average within each scenario.

| | Current | Matching market upside | Matching market downside |
|---|---|---|---|
| Bear weight | 25% | 25% (held) | 0% |
| Bull weight | 45% | 0% (at limit) | 45% (held) |
| Target | $19.44 | $13.97 | $23.32 |

Workbook three-scenario target for reference: $18.94.
