# Tushare U.S. source assessment — November 7, 2026

**Tushare can supply limited daily comparison data with the current token. It
has not established the consolidated trade/session coverage needed to replace
TAQ in this investigation.** This source-access item is complete.

| Check | Observed result |
| --- | --- |
| Local access | Existing configured token and SDK found; token never displayed or archived |
| `us_daily`, CSL, February 24–28, 2025 | Five rows returned with OHLC, volume, amount and VWAP |
| Next `us_daily` request, WSO | Explicit one-request-per-minute limit; no WSO observations returned |
| `us_daily_adj`, CSL, same dates | Explicit endpoint permission denial |
| U.S. trade/session evidence | No documented U.S. trade-level consolidated feed found in the reviewed catalog |
| Data qualification | Zero new qualified histories, catalog publications or strategy replays |

The [raw U.S. daily endpoint](https://tushare.pro/document/2?doc_id=254) documents
unadjusted prices and the daily fields above. The
[adjusted endpoint](https://tushare.pro/document/2?doc_id=338) additionally returns
an adjustment factor; its documented calculation multiplies the returned price
by that factor. Factors may change when corporate-action adjustments refresh.
The [permissions page](https://tushare.pro/document/1?doc_id=290) treats U.S.
historical daily access separately. Actual access here is bounded by the API
responses, not inferred from a general subscription or the existence of a token.

The [reviewed U.S. catalog](https://tushare.pro/document/2?doc_id=251) lists daily
stock/ETF, reference and fundamental endpoints. The U.S. pages do not specify
the CTA/UTP exchange/TRF scope, volume-eligible sale conditions, corrections,
regular-versus-extended-session totals or historical dissemination timestamps.
The daily volume label also does not explicitly define units/session boundaries;
do not import A-share lot conventions or infer a scale. This is a documented
coverage gap, not proof that the vendor could never offer another product.

Therefore these daily observations may help reconcile daily fields after their
definitions and identities are qualified. They cannot yet resolve why filtered
broker volume differs from the proposed consolidated full-session series.
The full ten-stock sample and agreement with the published histories were not
evaluated in this access item. No price adjustment or volume scaling was applied.

The first raw-daily HTTPS attempt failed at transport. A bounded Windows HTTPS
POST retry succeeded; credentials travelled only in stdin, never command-line
arguments. Acquisition stopped after the rate-limit response; the adjusted
permission denial was not retried. No purchases, permission changes, source
substitutions or shared-service changes occurred.

Local retention: `D:\systematic_trading_data\source-archives\tushare`. The two
run folders retain three compressed API responses, the failed transport receipt,
five CSL observations, exact token-free query parameters, capture times, hashes
and executed runners. Ten focused tests and Ruff pass. All response hashes,
successful row counts and executed-runner hashes verify. Original observations
remain source evidence; audit/publication is still required before research use.

[Assessment and receipts](assessment.json) · [Frozen scope/reuse decisions](protocol.json).
Next planned item: the bounded CRSP sample comparison and field-definition review.
Discuss this result before proceeding to that item.
