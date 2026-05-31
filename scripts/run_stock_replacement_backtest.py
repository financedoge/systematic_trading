from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from systematic_trading.backtest.comparison import (
    build_decision_diagnostics,
    build_market_data_audit,
    build_signal_diagnostics,
    compare_backtests,
    write_comparison_artifacts,
)
from systematic_trading.backtest.reporting import write_backtest_report
from systematic_trading.backtest.stock_replacement import (
    StockReplacementBacktestConfig,
    run_spy_replacement_backtest,
)
from systematic_trading.backtest.stored import StoredRiskParityBacktestConfig, run_stored_risk_parity_backtest
from systematic_trading.config import AppSettings
from systematic_trading.data.tushare import TushareUsDailyProvider
from systematic_trading.data.yahoo import YahooChartProvider
from systematic_trading.domain.enums import Currency
from systematic_trading.domain.market import FXRate, FundamentalSnapshot
from systematic_trading.research import (
    BENCHMARK_INSTRUMENTS,
    GLOBAL_ETF_UNIVERSE,
    MSCI_WORLD_PROXY_NAME,
    MSCI_WORLD_PROXY_SYMBOL,
    SPY_REPLACEMENT_SYMBOL,
    US_STOCK_REPLACEMENT_UNIVERSE,
    current_sota_definition,
    default_us_stock_symbols,
    instantiate_overlays,
)
from systematic_trading.storage.sqlite import SQLiteStore
from systematic_trading.valuation.ai import DEFAULT_OPENAI_MODEL, OpenAIStockFrameworkClient, OpenAIStockScreenError
from systematic_trading.valuation.framework import StockFrameworkScreen, rank_stock_reports
from systematic_trading.valuation.quantitative import build_quantitative_framework_screen
from systematic_trading.valuation.screener import (
    ai_screen_input_rows,
    build_heuristic_framework_screen,
    build_market_feature_snapshots,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rank US stock candidates with the probability framework and backtest replacing SPY with the top names."
    )
    parser.add_argument("--database", default="var/stock_replacement.db")
    parser.add_argument("--start-date", default="2012-01-01")
    parser.add_argument("--end-date", default="2026-04-29")
    parser.add_argument("--split-date", default="2023-01-01")
    parser.add_argument("--initial-cash-cnh", default="1000000")
    parser.add_argument("--output-dir", default="var/backtests/stock_framework_spy_replacement_2012")
    parser.add_argument("--ranking-path", default=None)
    parser.add_argument("--candidate-symbols", default="")
    parser.add_argument("--candidate-limit", type=int, default=0, help="0 means use the full default universe.")
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--stock-weighting", choices=["framework", "equal", "inverse-vol"], default="framework")
    parser.add_argument("--max-stock-weight-within-replacement", type=float, default=None)
    parser.add_argument(
        "--stock-selection-mode",
        choices=["static", "quantitative-point-in-time"],
        default="static",
    )
    parser.add_argument(
        "--fundamentals-path",
        default=None,
        help="Optional JSON file containing point-in-time FundamentalSnapshot records to upsert before ranking.",
    )
    parser.add_argument("--no-openai", action="store_true")
    parser.add_argument("--no-openai-web-search", action="store_true")
    parser.add_argument("--openai-model", default=DEFAULT_OPENAI_MODEL)
    parser.add_argument("--reasoning-effort", default="low", help="Use 'none' to omit the reasoning parameter.")
    parser.add_argument("--no-heuristic-fallback", action="store_true")
    parser.add_argument("--skip-fetch", action="store_true")
    parser.add_argument("--unadjusted-prices", action="store_true")
    parser.add_argument(
        "--market-data-source",
        choices=["tushare-first", "tushare", "yahoo"],
        default="tushare-first",
        help="Provider used when fetching missing US daily bars. FX still uses Yahoo CNY=X.",
    )
    args = parser.parse_args()

    start_date = date.fromisoformat(args.start_date)
    end_date = date.fromisoformat(args.end_date)
    split_date = date.fromisoformat(args.split_date)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    settings = AppSettings()
    database_path = Path(args.database) if args.database else settings.database_path
    store = SQLiteStore(database_path)
    store.initialize()
    if args.fundamentals_path:
        loaded = _load_fundamental_snapshots(store, Path(args.fundamentals_path))
        print(f"Loaded {loaded} fundamental snapshots")

    candidate_symbols = _candidate_symbols(args.candidate_symbols, args.candidate_limit)
    candidate_instruments = {
        symbol: US_STOCK_REPLACEMENT_UNIVERSE[symbol]
        for symbol in candidate_symbols
    }
    if not args.skip_fetch:
        _ensure_market_data(
            store=store,
            instruments={
                **GLOBAL_ETF_UNIVERSE,
                **BENCHMARK_INSTRUMENTS,
                **candidate_instruments,
            },
            start_date=start_date,
            end_date=end_date,
            adjusted_prices=not args.unadjusted_prices,
            market_data_source=args.market_data_source,
            tushare_token_path=settings.tushare_token_path,
        )

    features = build_market_feature_snapshots(
        {
            symbol: store.list_price_bars(symbol, start_date=start_date, end_date=end_date)
            for symbol in candidate_instruments
        },
        as_of=end_date,
    )
    fundamentals_by_symbol = {
        symbol: store.list_fundamental_snapshots(symbol, end_available_date=end_date)
        for symbol in candidate_instruments
    }
    if args.stock_selection_mode == "quantitative-point-in-time":
        screen = build_quantitative_framework_screen(
            instruments=candidate_instruments,
            features=features,
            fundamentals_by_symbol=fundamentals_by_symbol,
            as_of=end_date,
            top_n=None,
            universe_name="US stock replacement universe",
        )
    else:
        screen = _load_or_build_screen(
            args=args,
            output_dir=output_dir,
            candidate_instruments=candidate_instruments,
            features=features,
            as_of=end_date,
        )
    selected_reports = rank_stock_reports(screen.reports, top_n=args.top_n)
    selected_symbols = [report.ticker for report in selected_reports]
    backtest_symbols = candidate_symbols if args.stock_selection_mode == "quantitative-point-in-time" else selected_symbols
    ranking_json_path = output_dir / "stock_framework_rankings.json"
    ranking_md_path = output_dir / "stock_framework_rankings.md"
    ranking_json_path.write_text(json.dumps(screen.model_dump(mode="json"), indent=2), encoding="utf-8")
    ranking_md_path.write_text(_ranking_markdown(screen, selected_symbols), encoding="utf-8")

    baseline_definition = current_sota_definition()
    baseline_overlays = instantiate_overlays(baseline_definition)
    baseline_config = StoredRiskParityBacktestConfig(
        start_date=start_date,
        end_date=end_date,
        initial_cash_cnh=Decimal(args.initial_cash_cnh),
        sleeve_name=baseline_definition.sleeve_name,
    )
    candidate_config = StockReplacementBacktestConfig(
        start_date=start_date,
        end_date=end_date,
        initial_cash_cnh=Decimal(args.initial_cash_cnh),
        sleeve_name="sota-spy-replaced-by-stock-framework-top10",
        stock_weighting=args.stock_weighting,
        max_stock_weight_within_replacement=args.max_stock_weight_within_replacement,
        stock_selection_mode=args.stock_selection_mode.replace("-", "_"),
        dynamic_top_n=args.top_n if args.stock_selection_mode == "quantitative-point-in-time" else None,
    )

    baseline = run_stored_risk_parity_backtest(
        store=store,
        instruments=GLOBAL_ETF_UNIVERSE,
        config=baseline_config,
        target_overlays=baseline_overlays,
    )
    candidate = run_spy_replacement_backtest(
        store=store,
        stock_instruments=US_STOCK_REPLACEMENT_UNIVERSE,
        selected_symbols=backtest_symbols,
        config=candidate_config,
        stock_reports=selected_reports,
        base_target_overlays=baseline_overlays,
        fundamentals_by_symbol=fundamentals_by_symbol,
    )

    baseline_payload = _stable_backtest_payload(baseline.model_dump(mode="json"))
    candidate_payload = _stable_backtest_payload(candidate.model_dump(mode="json"))
    baseline_path = output_dir / f"{baseline_definition.key}.json"
    candidate_path = output_dir / "stock-framework-spy-replacement-top10.json"
    baseline_path.write_text(json.dumps(baseline_payload, indent=2), encoding="utf-8")
    candidate_path.write_text(json.dumps(candidate_payload, indent=2), encoding="utf-8")

    comparison = compare_backtests(
        baseline=baseline_payload,
        candidate=candidate_payload,
        split_date=split_date,
        baseline_name=baseline_definition.name,
        candidate_name="SOTA with SPY replaced by framework top 10 stocks",
    )
    prices_by_symbol = _prices_by_symbol(
        store,
        sorted(set(GLOBAL_ETF_UNIVERSE) | set(selected_symbols)),
    )
    signal_diagnostics = build_signal_diagnostics(
        baseline=baseline_payload,
        candidate=candidate_payload,
        prices_by_symbol=prices_by_symbol,
        split_date=split_date,
        signal_name="stock-framework-spy-replacement",
    )
    market_data_audit = build_market_data_audit(
        prices_by_symbol=prices_by_symbol,
        required_dates=[date.fromisoformat(point["trade_date"]) for point in candidate_payload["nav_series"]],
        source_name=f"SQLite {database_path}",
        adjusted_prices=not args.unadjusted_prices,
    )
    artifacts = write_comparison_artifacts(
        comparison=comparison,
        output_dir=output_dir,
        stem="comparison",
        signal_diagnostics=signal_diagnostics,
        market_data_audit=market_data_audit,
        decision_diagnostics=build_decision_diagnostics(signal_diagnostics),
        model_structure=_model_structure(
            baseline_definition=baseline_definition,
            selected_symbols=selected_symbols,
            stock_weighting=args.stock_weighting,
            stock_selection_mode=args.stock_selection_mode,
        ),
    )
    report = write_backtest_report(
        result_path=candidate_path,
        output_path=output_dir / "stock-framework-spy-replacement-top10.html",
        database_path=database_path,
        split_date=split_date,
        benchmark_nav_series=baseline_payload["nav_series"],
        benchmark_name=baseline_definition.name,
        extra_benchmarks=[{"id": "msci_world", "name": MSCI_WORLD_PROXY_NAME, "symbol": MSCI_WORLD_PROXY_SYMBOL}],
        signal_diagnostics=signal_diagnostics,
    )

    print(ranking_json_path)
    print(ranking_md_path)
    print(baseline_path)
    print(candidate_path)
    print(artifacts.markdown_path)
    print(artifacts.json_path)
    print(report.output_path)
    print("Selected:", ", ".join(selected_symbols))


def _load_fundamental_snapshots(store: SQLiteStore, path: Path) -> int:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        records = []
        for symbol, values in raw.items():
            if not isinstance(values, list):
                raise ValueError(f"Fundamental snapshot entry for {symbol} must be a list.")
            for value in values:
                if not isinstance(value, dict):
                    raise ValueError(f"Fundamental snapshot entry for {symbol} must be an object.")
                records.append({"symbol": symbol, **value})
    elif isinstance(raw, list):
        records = raw
    else:
        raise ValueError("--fundamentals-path must contain either a list of snapshots or a symbol-to-list mapping.")

    count = 0
    for record in records:
        snapshot = FundamentalSnapshot.model_validate(record)
        store.upsert_fundamental_snapshot(snapshot)
        count += 1
    return count


def _candidate_symbols(value: str, candidate_limit: int) -> list[str]:
    if value.strip():
        symbols = [item.strip().upper() for item in value.split(",") if item.strip()]
    else:
        symbols = default_us_stock_symbols()
    unknown = sorted(set(symbols) - set(US_STOCK_REPLACEMENT_UNIVERSE))
    if unknown:
        raise ValueError(f"Unknown default stock-universe symbols: {', '.join(unknown)}")
    if candidate_limit > 0:
        return symbols[:candidate_limit]
    return symbols


def _load_or_build_screen(
    *,
    args: argparse.Namespace,
    output_dir: Path,
    candidate_instruments: dict[str, object],
    features: dict[str, object],
    as_of: date,
) -> StockFrameworkScreen:
    ranking_path = Path(args.ranking_path) if args.ranking_path else None
    if ranking_path is not None and ranking_path.exists():
        return StockFrameworkScreen.model_validate_json(ranking_path.read_text(encoding="utf-8"))

    if not args.no_openai:
        try:
            client = OpenAIStockFrameworkClient(model=args.openai_model)
            return client.score_candidates(
                as_of=as_of,
                universe_name="US stock replacement universe",
                candidates=ai_screen_input_rows(instruments=candidate_instruments, features=features),
                use_web_search=not args.no_openai_web_search,
                reasoning_effort=None if args.reasoning_effort.lower() == "none" else args.reasoning_effort,
            )
        except OpenAIStockScreenError as exc:
            failure_path = output_dir / "openai_stock_screen_error.txt"
            failure_path.write_text(str(exc), encoding="utf-8")
            if args.no_heuristic_fallback:
                raise

    return build_heuristic_framework_screen(
        instruments=candidate_instruments,
        features=features,
        as_of=as_of,
        top_n=None,
        universe_name="US stock replacement universe",
    )


def _ensure_market_data(
    *,
    store: SQLiteStore,
    instruments: Mapping[str, Any],
    start_date: date,
    end_date: date,
    adjusted_prices: bool,
    market_data_source: str,
    tushare_token_path: Path,
) -> None:
    yahoo_provider = YahooChartProvider(adjust_prices=adjusted_prices)
    tushare_provider = (
        TushareUsDailyProvider(token_path=tushare_token_path, adjusted=adjusted_prices)
        if market_data_source in {"tushare-first", "tushare"}
        else None
    )
    for symbol, instrument in sorted(instruments.items()):
        store.upsert_instrument(instrument)
        bars = store.list_price_bars(symbol, start_date=start_date, end_date=end_date)
        if _range_is_covered(bars, start_date=start_date, end_date=end_date):
            continue
        fetched_bars = _fetch_market_bars(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            market_data_source=market_data_source,
            tushare_provider=tushare_provider,
            yahoo_provider=yahoo_provider,
        )
        for bar in fetched_bars:
            store.upsert_price_bar(symbol, bar)

    fx_rates = store.list_fx_rates(Currency.USD, start_date=start_date, end_date=end_date)
    if not (fx_rates and fx_rates[0].rate_date <= start_date and fx_rates[-1].rate_date >= end_date):
        for bar in YahooChartProvider().fetch_daily_bars("CNY=X", start_date, end_date):
            store.upsert_fx_rate(
                FXRate(
                    rate_date=bar.trade_date,
                    base_currency=Currency.USD,
                    quote_currency=Currency.CNH,
                    rate=bar.close,
                )
            )


def _fetch_market_bars(
    *,
    symbol: str,
    start_date: date,
    end_date: date,
    market_data_source: str,
    tushare_provider: TushareUsDailyProvider | None,
    yahoo_provider: YahooChartProvider,
) -> list[Any]:
    if market_data_source in {"tushare-first", "tushare"} and tushare_provider is not None:
        try:
            bars = tushare_provider.fetch_daily_bars([symbol], start_date, end_date).get(symbol, [])
            if bars:
                print(f"{symbol}: fetched {len(bars)} bars from Tushare")
                return bars
            if market_data_source == "tushare":
                raise ValueError(f"Tushare returned no daily bars for {symbol}.")
            print(f"{symbol}: Tushare returned no daily bars; falling back to Yahoo")
        except Exception as exc:
            if market_data_source == "tushare":
                raise
            print(f"{symbol}: Tushare fetch failed ({_safe_exception_message(exc)}); falling back to Yahoo")

    bars = yahoo_provider.fetch_daily_bars(symbol, start_date, end_date)
    if not bars:
        raise ValueError(f"Yahoo returned no daily bars for {symbol}.")
    print(f"{symbol}: fetched {len(bars)} bars from Yahoo")
    return bars


def _range_is_covered(bars: Sequence[Any], *, start_date: date, end_date: date) -> bool:
    if not bars:
        return False
    return 0 <= (bars[0].trade_date - start_date).days <= 7 and bars[-1].trade_date >= end_date


def _safe_exception_message(exc: Exception) -> str:
    message = str(exc).strip() or exc.__class__.__name__
    return message.encode("ascii", errors="backslashreplace").decode("ascii")


def _prices_by_symbol(store: SQLiteStore, symbols: list[str]) -> dict[str, dict[date, float]]:
    return {
        symbol: {bar.trade_date: float(bar.close) for bar in store.list_price_bars(symbol)}
        for symbol in symbols
    }


def _stable_backtest_payload(payload: dict[str, Any]) -> dict[str, Any]:
    for proposal in payload.get("proposals", []):
        as_of = str(proposal["as_of"])
        sleeve = str(proposal["sleeve"])
        proposal["proposal_id"] = hashlib.sha1(f"{sleeve}:{as_of}".encode("utf-8")).hexdigest()[:12]
        proposal["created_at"] = f"{as_of}T00:00:00Z"
    return payload


def _ranking_markdown(screen: StockFrameworkScreen, selected_symbols: list[str]) -> str:
    selected = set(selected_symbols)
    lines = [
        "# Stock Framework Rankings",
        "",
        f"- As of: {screen.as_of}",
        f"- Framework: {screen.framework_version}",
        f"- Model: {screen.model}",
        f"- Universe: {screen.universe}",
        f"- Selected top {len(selected_symbols)}: {', '.join(selected_symbols)}",
        "",
    ]
    if screen.notes:
        lines.extend(["Notes:", *[f"- {note}" for note in screen.notes], ""])
    lines.extend(
        [
            "| Rank | Use | Ticker | Company | Bucket | Score | Upside | Bear Downside | Quality | Thesis | Main Risk |",
            "| ---: | --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |",
        ]
    )
    for rank, report in enumerate(rank_stock_reports(screen.reports), start=1):
        use = "top10" if report.ticker in selected else "watch"
        lines.append(
            f"| {rank} | {use} | {report.ticker} | {report.company} | {report.opportunity_bucket} | "
            f"{report.total_score:.1f} | {report.expected_upside:.1%} | {report.bear_case_downside:.1%} | "
            f"{report.quality_score:.1f} | {report.key_thesis} | {report.main_risk} |"
        )
    lines.append("")
    return "\n".join(lines)


def _model_structure(
    *,
    baseline_definition: Any,
    selected_symbols: list[str],
    stock_weighting: str,
    stock_selection_mode: str,
) -> dict[str, Any]:
    from systematic_trading.research import strategy_model_card

    candidate_definition = {
        "key": "stock_framework_spy_replacement_top10",
        "name": "SOTA with SPY replaced by framework top 10 stocks",
        "sleeveName": "sota-spy-replaced-by-stock-framework-top10",
        "state": "research",
        "description": (
            f"Monthly SOTA ETF model where the {SPY_REPLACEMENT_SYMBOL} target is expanded into "
            f"{len(selected_symbols)} stock selections ranked by the probability-based framework. "
            f"Selection mode: {stock_selection_mode}."
        ),
        "promotedOn": None,
        "overlays": [
            {
                "kind": "stock_replacement",
                "parameters": {
                    "symbols": ",".join(selected_symbols),
                    "weighting": stock_weighting,
                    "selectionMode": stock_selection_mode,
                },
            }
        ],
    }
    layer_diagram = "\n".join(
        [
            "flowchart LR",
            '  L1["Adjusted market data<br/>ETFs, selected stocks, USD/CNH FX"]',
            '  L2["Monthly SOTA ETF targets<br/>Risk parity plus registered relative-momentum overlay"]',
            f'  L3["Replace {SPY_REPLACEMENT_SYMBOL}<br/>Expand the US ETF target into {", ".join(selected_symbols)}"]',
            f'  L4["Stock basket weights<br/>{stock_weighting} weighting inside the replaced sleeve"]',
            '  L5["Final target weights<br/>Feed daily execution backtest"]',
            "  L1 --> L2",
            "  L2 --> L3",
            "  L3 --> L4",
            "  L4 --> L5",
        ]
    )
    decision_tree = "\n".join(
        [
            "flowchart TD",
            '  A(["Monthly SOTA ETF target"]) --> B{"Target symbol is SPY?"}',
            '  B -- "No" --> C["Keep ETF target unchanged"]',
            f'  B -- "Yes" --> D["Split SPY weight across {len(selected_symbols)} selected stocks"]',
            f'  D --> E["Use {stock_weighting} stock-basket weighting"]',
            '  C --> F(["Final candidate targets"])',
            '  E --> F',
        ]
    )
    return {
        "baseline": strategy_model_card(baseline_definition),
        "candidate": {
            "definition": candidate_definition,
            "layers": [],
            "layerDiagram": layer_diagram,
            "decisionTree": decision_tree,
        },
    }


if __name__ == "__main__":
    main()
