# API Workflow

## Stateful operator flow

1. Register or update watchlist instruments with `PUT /api/v1/watchlist/instruments/{symbol}`.
2. Attach thesis memos with `PUT /api/v1/watchlist/theses/{symbol}`.
3. Review the combined watchlist via `GET /api/v1/watchlist`.
4. Store normalized price bars with `PUT /api/v1/market-data/bars/{symbol}`.
5. Store FX rates with `PUT /api/v1/market-data/fx-rates`.
6. Query stored price bars with `GET /api/v1/market-data/bars/{symbol}`.
7. Query stored FX rates with `GET /api/v1/market-data/fx-rates?base_currency=USD`.
8. Estimate stored close-to-close volatility with `GET /api/v1/market-data/volatility/{symbol}`.
9. Preview a beta rebalance using `POST /api/v1/proposals/risk-parity-preview`.
10. Persist a proposal to the approval queue using `POST /api/v1/proposals/risk-parity-queue`.
11. List queued proposals with `GET /api/v1/proposals?status=pending`.
12. Approve or reject a queued proposal using `POST /api/v1/proposals/{proposal_id}/decisions`.
13. In the operator dashboard, approval calls `POST /api/v1/proposals/{proposal_id}/approve-and-submit` to approve and submit TWAP paper orders in one backend operation.
14. Use `POST /api/v1/execution/interactive-brokers/proposals/{proposal_id}/submit` with `confirm_submit=true` for CLI/API-controlled submission or failed-order resubmission.
15. List persisted broker order records with `GET /api/v1/execution/interactive-brokers/orders?proposal_id={proposal_id}`.

## Platform manifest endpoints

- `GET /api/v1/platform/manifest` returns the high-level platform capabilities.
- `GET /api/v1/data-sources` returns the configured and planned data-source registry.
- `GET /api/v1/execution/interactive-brokers/profiles` returns paper/live broker environment profiles and safeguards.
- `POST /api/v1/proposals/{proposal_id}/approve-and-submit` approves a queued proposal and routes TWAP paper orders in one backend operation.
- `POST /api/v1/execution/interactive-brokers/proposals/{proposal_id}/submit` validates or routes approved proposals.
- `GET /api/v1/execution/interactive-brokers/orders` returns local broker order records.

## Local persistence

- Default SQLite path: `var/systematic_trading.db`
- Stored entities: watchlist instruments, thesis memos, normalized price bars, FX rates, queued proposals, approval decisions, broker order records
