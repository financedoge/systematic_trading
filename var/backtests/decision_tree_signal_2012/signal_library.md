# Signal Library

This is the code-backed feature library used by research overlays and the decision-tree trainer.

| Feature ID | Family | Name | Lookback | Description |
| --- | --- | --- | ---: | --- |
| `mom_21` | price_trend | 21-bar momentum | 21 | Short-term price return. |
| `mom_63` | price_trend | 63-bar momentum | 63 | Quarterly price return. |
| `mom_126` | price_trend | 126-bar momentum | 126 | Medium-term price return. |
| `mom_252` | price_trend | 252-bar momentum | 252 | Long-term price return. |
| `mom_378` | price_trend | 378-bar momentum | 378 | Extended trend return. |
| `relative_momentum_126_252` | price_trend | 126/252 relative momentum | 252 | SOTA-style blend: 45% 126-bar return plus 55% 252-bar return. |
| `above_ma_63` | price_trend | Above 63-bar MA | 63 | 1 when close is above its 63-bar average. |
| `above_ma_252` | price_trend | Above 252-bar MA | 252 | 1 when close is above its 252-bar average. |
| `reversal_21` | mean_reversion | 21-bar reversal | 21 | Negative of 21-bar momentum. |
| `mean_reversion_ma_63` | mean_reversion | 63-bar MA reversion | 63 | Negative of price deviation from the 63-bar moving average. |
| `up_volume_share_21` | volume | 21-bar up-volume share | 21 | Share of recent volume traded on up-close days. |
| `signed_volume_pressure_21_126` | volume | Signed volume pressure | 126 | 21-bar volume acceleration, positive when short momentum is positive and negative when it is weak. |
| `vol_ratio_21_252` | risk_regime | 21/252 volatility ratio | 252 | Fast realized volatility divided by slow realized volatility. |
| `drawdown_252` | risk_regime | 252-bar drawdown | 252 | Drawdown from the trailing 252-bar high. |
| `valuation_score` | valuation | Valuation score | n/a | External score map. Positive means cheaper or more attractive. |
| `macro_growth_score` | macro | Macro growth score | n/a | External country score map. Positive means stronger growth or policy backdrop. |