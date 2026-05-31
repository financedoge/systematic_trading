from __future__ import annotations

import argparse
import hashlib
import html
import json
import shutil
import sys
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any


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
from systematic_trading.backtest.stored import (
    StoredRiskParityBacktestConfig,
    run_dynamic_risk_parity_backtest,
    run_stored_risk_parity_backtest,
)
from systematic_trading.config import AppSettings
from systematic_trading.research import (
    MSCI_WORLD_PROXY_NAME,
    MSCI_WORLD_PROXY_SYMBOL,
    build_model_structure_comparison,
    current_sota_definition,
    instruments_for_definition,
    instantiate_overlays,
    risk_parity_definition,
    strategy_model_card,
)
from systematic_trading.storage.sqlite import SQLiteStore


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export the current SOTA backtest, benchmark-only backtest, comparison, and model diagram."
    )
    parser.add_argument("--database", default=None)
    parser.add_argument("--start-date", default="2012-01-01")
    parser.add_argument("--end-date", default="2026-04-29")
    parser.add_argument("--split-date", default="2023-01-01")
    parser.add_argument("--initial-cash-cnh", default="1000000")
    parser.add_argument("--output-dir", default="var/backtests/sota_current")
    parser.add_argument(
        "--no-history",
        action="store_true",
        help="Skip writing the immutable history snapshot under the output directory.",
    )
    args = parser.parse_args()

    settings = AppSettings()
    database_path = Path(args.database) if args.database else settings.database_path
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    _clean_output_dir(output_dir)
    store = SQLiteStore(database_path)
    store.initialize()

    start_date = date.fromisoformat(args.start_date)
    end_date = date.fromisoformat(args.end_date)
    split_date = date.fromisoformat(args.split_date)
    initial_cash_cnh = Decimal(args.initial_cash_cnh)

    benchmark_definition = risk_parity_definition()
    sota_definition = current_sota_definition()
    sota_instruments = _instruments_for_definition(sota_definition)
    benchmark = _run_definition_backtest(
        store=store,
        instruments=sota_instruments,
        definition=sota_definition,
        config=StoredRiskParityBacktestConfig(
            start_date=start_date,
            end_date=end_date,
            initial_cash_cnh=initial_cash_cnh,
            sleeve_name=benchmark_definition.sleeve_name,
        ),
        target_overlays=(),
    )
    sota = _run_definition_backtest(
        store=store,
        instruments=sota_instruments,
        definition=sota_definition,
        config=StoredRiskParityBacktestConfig(
            start_date=start_date,
            end_date=end_date,
            initial_cash_cnh=initial_cash_cnh,
            sleeve_name=sota_definition.sleeve_name,
        ),
        target_overlays=instantiate_overlays(sota_definition),
    )

    benchmark_payload = _stable_backtest_payload(benchmark.model_dump(mode="json"))
    sota_payload = _stable_backtest_payload(sota.model_dump(mode="json"))
    benchmark_path = output_dir / f"{benchmark_definition.key}.json"
    sota_path = output_dir / f"{sota_definition.key}.json"
    benchmark_path.write_text(json.dumps(benchmark_payload, indent=2), encoding="utf-8")
    sota_path.write_text(json.dumps(sota_payload, indent=2), encoding="utf-8")

    comparison = compare_backtests(
        baseline=benchmark_payload,
        candidate=sota_payload,
        split_date=split_date,
        baseline_name=benchmark_definition.name,
        candidate_name=sota_definition.name,
    )
    prices_by_symbol = _prices_by_symbol(store, sorted(set(sota_instruments) | {MSCI_WORLD_PROXY_SYMBOL}))
    signal_diagnostics = build_signal_diagnostics(
        baseline=benchmark_payload,
        candidate=sota_payload,
        prices_by_symbol=prices_by_symbol,
        split_date=split_date,
        signal_name=sota_definition.key,
    )
    market_data_audit = build_market_data_audit(
        prices_by_symbol={symbol: prices_by_symbol[symbol] for symbol in sota_instruments},
        required_dates=[date.fromisoformat(point["trade_date"]) for point in sota_payload["nav_series"]],
        source_name=f"SQLite {database_path}",
        adjusted_prices=True,
    )
    comparison_artifacts = write_comparison_artifacts(
        comparison=comparison,
        output_dir=output_dir,
        stem="sota_vs_benchmark",
        signal_diagnostics=signal_diagnostics,
        market_data_audit=market_data_audit,
        decision_diagnostics=build_decision_diagnostics(signal_diagnostics),
        model_structure=build_model_structure_comparison(
            baseline=benchmark_definition,
            candidate=sota_definition,
        ),
    )
    benchmark_report = write_backtest_report(
        result_path=benchmark_path,
        output_path=output_dir / f"{benchmark_definition.key}.html",
        database_path=database_path,
        split_date=split_date,
        benchmark_symbol=MSCI_WORLD_PROXY_SYMBOL,
        benchmark_name=MSCI_WORLD_PROXY_NAME,
    )
    sota_report = write_backtest_report(
        result_path=sota_path,
        output_path=output_dir / f"{sota_definition.key}.html",
        database_path=database_path,
        split_date=split_date,
        benchmark_nav_series=benchmark_payload["nav_series"],
        benchmark_name=benchmark_definition.name,
        extra_benchmarks=[{"id": "msci_world", "name": MSCI_WORLD_PROXY_NAME, "symbol": MSCI_WORLD_PROXY_SYMBOL}],
        signal_diagnostics=signal_diagnostics,
    )
    model_path = output_dir / "sota_model.html"
    _write_model_html(
        path=model_path,
        benchmark_card=strategy_model_card(benchmark_definition),
        sota_card=strategy_model_card(sota_definition),
        comparison=comparison,
    )
    readme_path = output_dir / "README.md"
    history_index_path = output_dir / "history" / "index.md"
    readme_path.write_text(
        _readme(
            benchmark_definition=benchmark_definition,
            sota_definition=sota_definition,
            comparison=comparison,
            paths={
                "benchmark_json": benchmark_path,
                "benchmark_html": benchmark_report.output_path,
                "sota_json": sota_path,
                "sota_html": sota_report.output_path,
                "comparison_json": comparison_artifacts.json_path,
                "comparison_md": comparison_artifacts.markdown_path,
                "model_html": model_path,
                "history_index": history_index_path,
            },
        ),
        encoding="utf-8",
    )
    history_paths: list[Path] = []
    if not args.no_history:
        history_paths = _write_history_snapshot(
            output_dir=output_dir,
            sota_definition=sota_definition,
            comparison=comparison,
            paths={
                "readme": readme_path,
                "benchmark_json": benchmark_path,
                "benchmark_html": benchmark_report.output_path,
                "sota_json": sota_path,
                "sota_html": sota_report.output_path,
                "comparison_json": comparison_artifacts.json_path,
                "comparison_md": comparison_artifacts.markdown_path,
                "model_html": model_path,
            },
        )

    for path in [
        benchmark_path,
        benchmark_report.output_path,
        sota_path,
        sota_report.output_path,
        comparison_artifacts.json_path,
        comparison_artifacts.markdown_path,
        model_path,
        readme_path,
        *history_paths,
    ]:
        print(path)


def _instruments_for_definition(definition: Any) -> dict[str, Any]:
    return dict(instruments_for_definition(definition))


def _clean_output_dir(output_dir: Path) -> None:
    managed_patterns = [
        "README.md",
        "risk_parity.json",
        "risk_parity.html",
        "sota_*.json",
        "sota_*.html",
        "sota_vs_benchmark.json",
        "sota_vs_benchmark.md",
        "sota_model.html",
    ]
    output_root = output_dir.resolve()
    for pattern in managed_patterns:
        for path in output_dir.glob(pattern):
            if path.is_file() and path.resolve().parent == output_root:
                path.unlink()


def _run_definition_backtest(
    *,
    store: SQLiteStore,
    instruments: dict[str, Any],
    definition: Any,
    config: StoredRiskParityBacktestConfig,
    target_overlays: tuple[Any, ...] | list[Any],
) -> Any:
    if getattr(definition, "scheduler", "static_monthly") == "dynamic_monthly":
        return run_dynamic_risk_parity_backtest(
            store=store,
            instruments=instruments,
            config=config,
            target_overlays=target_overlays,
        )
    return run_stored_risk_parity_backtest(
        store=store,
        instruments=instruments,
        config=config,
        target_overlays=target_overlays,
    )


def _write_history_snapshot(
    *,
    output_dir: Path,
    sota_definition: Any,
    comparison: dict[str, Any],
    paths: dict[str, Path],
) -> list[Path]:
    history_root = output_dir / "history"
    promoted_on = getattr(sota_definition, "promoted_on", None) or date.today().isoformat()
    entry_dir = history_root / f"{promoted_on}_{sota_definition.key}"
    entry_dir.mkdir(parents=True, exist_ok=True)

    copied_files: dict[str, str] = {}
    for key, source in paths.items():
        destination = entry_dir / source.name
        shutil.copy2(source, destination)
        copied_files[key] = destination.relative_to(output_dir).as_posix()

    metadata_path = entry_dir / "metadata.json"
    metadata = {
        "key": sota_definition.key,
        "name": sota_definition.name,
        "promotedOn": promoted_on,
        "generatedAt": datetime.now(tz=UTC).isoformat(),
        "source": "export_sota_artifacts.py",
        "metrics": _history_metrics(comparison),
        "files": copied_files,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    index_json_path, index_md_path = _write_history_index(history_root)
    return [metadata_path, index_json_path, index_md_path]


def _write_history_index(history_root: Path) -> tuple[Path, Path]:
    entries = []
    for metadata_path in sorted(history_root.glob("*/metadata.json")):
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["entryDir"] = metadata_path.parent.name
        entries.append(metadata)
    entries.sort(key=lambda item: (str(item.get("promotedOn") or ""), str(item.get("key") or "")), reverse=True)

    index_json_path = history_root / "index.json"
    index_md_path = history_root / "index.md"
    index_json_path.write_text(json.dumps({"entries": entries}, indent=2), encoding="utf-8")
    index_md_path.write_text(_history_index_markdown(entries), encoding="utf-8")
    return index_json_path, index_md_path


def _history_metrics(comparison: dict[str, Any]) -> dict[str, Any]:
    metrics = comparison["metrics"]
    return {
        "dateRange": comparison["dateRange"],
        "splitDate": comparison["splitDate"],
        "full": _history_metric_row(metrics["full"]),
        "outOfSample": _history_metric_row(metrics["out_of_sample"]),
    }


def _history_metric_row(metrics: dict[str, Any]) -> dict[str, Any]:
    candidate = metrics["candidate"]
    active = metrics.get("active", {})
    delta = metrics.get("delta", {})
    return {
        "return": candidate.get("return"),
        "annualizedReturn": candidate.get("annualizedReturn"),
        "maxDrawdown": candidate.get("maxDrawdown"),
        "sharpe": candidate.get("sharpe"),
        "sortino": candidate.get("sortino"),
        "calmar": candidate.get("calmar"),
        "alpha": delta.get("return"),
        "informationRatio": active.get("informationRatio"),
        "trackingError": active.get("trackingError"),
    }


def _history_index_markdown(entries: list[dict[str, Any]]) -> str:
    lines = [
        "# SOTA History",
        "",
        "Immutable promotion snapshots generated by `scripts/export_sota_artifacts.py`.",
        "",
        "| Promoted | Strategy | OOS Ann. Return | OOS Sharpe | OOS Calmar | OOS Max DD | OOS IR | Files |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for entry in entries:
        oos = entry.get("metrics", {}).get("outOfSample", {})
        files = entry.get("files", {})
        file_links = []
        for label, key in [
            ("readme", "readme"),
            ("report", "sota_html"),
            ("model", "model_html"),
            ("comparison", "comparison_md"),
        ]:
            if key in files:
                file_links.append(f"[{label}]({_history_index_link(files[key])})")
        lines.append(
            "| "
            + " | ".join(
                [
                    str(entry.get("promotedOn", "")),
                    str(entry.get("name", "")),
                    _fmt_pct(oos.get("annualizedReturn")),
                    _fmt_num(oos.get("sharpe")),
                    _fmt_num(oos.get("calmar")),
                    _fmt_pct(oos.get("maxDrawdown")),
                    _fmt_num(oos.get("informationRatio")),
                    ", ".join(file_links),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def _history_index_link(path: str) -> str:
    prefix = "history/"
    return path[len(prefix) :] if path.startswith(prefix) else path


def _stable_backtest_payload(payload: dict[str, Any]) -> dict[str, Any]:
    for proposal in payload.get("proposals", []):
        as_of = str(proposal["as_of"])
        sleeve = str(proposal["sleeve"])
        proposal["proposal_id"] = hashlib.sha1(f"{sleeve}:{as_of}".encode("utf-8")).hexdigest()[:12]
        proposal["created_at"] = f"{as_of}T00:00:00Z"
    return payload


def _prices_by_symbol(store: SQLiteStore, symbols: list[str]) -> dict[str, dict[date, float]]:
    return {
        symbol: {bar.trade_date: float(bar.close) for bar in store.list_price_bars(symbol)}
        for symbol in symbols
    }


def _write_model_html(
    *,
    path: Path,
    benchmark_card: dict[str, Any],
    sota_card: dict[str, Any],
    comparison: dict[str, Any],
) -> None:
    full = comparison["metrics"]["full"]
    oos = comparison["metrics"]["out_of_sample"]
    content = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Current SOTA Model</title>
  <script type="module">import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs'; mermaid.initialize({{startOnLoad: true}});</script>
  <style>
    body {{ margin: 0; font-family: Inter, Segoe UI, Arial, sans-serif; color: #172033; background: #f6f8fb; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 28px; }}
    h1, h2, h3 {{ margin: 0; }}
    h1 {{ font-size: 30px; }}
    h2 {{ margin-top: 28px; font-size: 21px; }}
    h3 {{ margin-top: 18px; font-size: 16px; }}
    .subtle {{ color: #607089; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; margin: 18px 0 24px; }}
    .stat, .panel {{ background: #fff; border: 1px solid #dce4ef; border-radius: 8px; box-shadow: 0 8px 20px rgba(30, 45, 70, .06); }}
    .stat {{ padding: 14px 16px; }}
    .stat span {{ display: block; color: #607089; font-size: 12px; margin-bottom: 6px; }}
    .stat strong {{ font-size: 22px; }}
    .panel {{ padding: 18px; margin-top: 14px; overflow-x: auto; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
    th, td {{ border-bottom: 1px solid #e6edf5; padding: 8px 10px; text-align: left; vertical-align: top; }}
    th {{ color: #607089; font-size: 12px; text-transform: uppercase; }}
    code, pre {{ font-family: Consolas, Monaco, monospace; }}
    pre {{ background: #101828; color: #e5edf8; padding: 14px; border-radius: 6px; overflow-x: auto; }}
    .mermaid {{ background: #fff; border: 1px solid #e6edf5; border-radius: 6px; padding: 12px; margin-top: 10px; }}
  </style>
</head>
<body>
<main>
  <h1>{_esc(sota_card['definition']['name'])}</h1>
  <p class="subtle">Canonical current SOTA model card and benchmark comparison. Generated from the strategy catalog.</p>
  <section class="grid">
    <div class="stat"><span>Full Alpha vs Benchmark</span><strong>{_fmt_pct(full['delta']['return'])}</strong></div>
    <div class="stat"><span>Full Information Ratio</span><strong>{_fmt_num(full['active']['informationRatio'])}</strong></div>
    <div class="stat"><span>OOS Alpha vs Benchmark</span><strong>{_fmt_pct(oos['delta']['return'])}</strong></div>
    <div class="stat"><span>OOS Information Ratio</span><strong>{_fmt_num(oos['active']['informationRatio'])}</strong></div>
  </section>
  {_card_section('Benchmark Only', benchmark_card)}
  {_card_section('SOTA Strategy', sota_card)}
</main>
</body>
</html>
"""
    path.write_text(content, encoding="utf-8")


def _card_section(title: str, card: dict[str, Any]) -> str:
    definition = card["definition"]
    params = []
    for overlay in definition.get("overlays", []):
        for key, value in overlay.get("parameters", {}).items():
            params.append((overlay["kind"], key, value))
    param_rows = "\n".join(
        f"<tr><td>{_esc(kind)}</td><td>{_esc(key)}</td><td><code>{_esc(str(value))}</code></td></tr>"
        for kind, key, value in params
    )
    params_html = (
        "<h3>Parameters</h3><table><thead><tr><th>Overlay</th><th>Parameter</th><th>Value</th></tr></thead>"
        f"<tbody>{param_rows}</tbody></table>"
        if params
        else "<p class=\"subtle\">No overlay parameters; this is the benchmark-only risk-parity model.</p>"
    )
    return f"""
  <section class="panel">
    <h2>{_esc(title)}</h2>
    <p><strong>{_esc(definition['name'])}</strong></p>
    <p class="subtle">{_esc(definition['description'])}</p>
    <h3>Layer Diagram</h3>
    <div class="mermaid">{_esc(card['layerDiagram'])}</div>
    <h3>Decision Tree</h3>
    <div class="mermaid">{_esc(card['decisionTree'])}</div>
    {params_html}
    <h3>Raw Mermaid</h3>
    <pre>{_esc(card['decisionTree'])}</pre>
  </section>
"""


def _readme(
    *,
    benchmark_definition: Any,
    sota_definition: Any,
    comparison: dict[str, Any],
    paths: dict[str, Path],
) -> str:
    full = comparison["metrics"]["full"]
    oos = comparison["metrics"]["out_of_sample"]
    lines = [
        "# Current SOTA Backtest",
        "",
        f"- Strategy: {sota_definition.name}",
        f"- Benchmark only: {benchmark_definition.name}",
        f"- Range: {comparison['dateRange']['start']} to {comparison['dateRange']['end']}",
        f"- OOS split: {comparison['splitDate']}",
        f"- Full alpha: {_fmt_pct(full['delta']['return'])}",
        f"- Full information ratio: {_fmt_num(full['active']['informationRatio'])}",
        f"- OOS alpha: {_fmt_pct(oos['delta']['return'])}",
        f"- OOS information ratio: {_fmt_num(oos['active']['informationRatio'])}",
        "",
        "## Files",
        "",
    ]
    for label, path in paths.items():
        lines.append(f"- `{label}`: `{path}`")
    lines.append("")
    return "\n".join(lines)


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def _fmt_pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2%}"


def _fmt_num(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"


if __name__ == "__main__":
    main()
