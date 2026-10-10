"""Presentation-only asset labels shared by app pages and standalone reports."""

import json


def registered_asset_names() -> dict[str, str]:
    from systematic_trading.research.all_weather_universe import ALL_WEATHER_ETF_UNIVERSE
    from systematic_trading.research.etf_universe import BENCHMARK_INSTRUMENTS, MULTI_ASSET_ETF_UNIVERSE, RESEARCH_SECTOR_ETFS
    from systematic_trading.research.stock_universe import US_STOCK_REPLACEMENT_UNIVERSE

    instruments = {
        **US_STOCK_REPLACEMENT_UNIVERSE,
        **MULTI_ASSET_ETF_UNIVERSE,
        **ALL_WEATHER_ETF_UNIVERSE,
        **BENCHMARK_INSTRUMENTS,
        **RESEARCH_SECTOR_ETFS,
    }
    # Recorder canary outside the trading universes; issuer display name checked
    # 2026-10-02: https://www.invesco.com/qqq-etf/en/home.html
    return {"QQQ": "Invesco QQQ ETF", **{symbol: item.name for symbol, item in instruments.items()},
            "CASH": "Cash balance"}


def asset_names_javascript() -> str:
    # Embedded data also works in downloaded reports without a network request.
    payload = json.dumps(registered_asset_names(), ensure_ascii=True).replace("<", "\\u003c")
    return _JAVASCRIPT.replace("__ASSET_NAMES__", payload)


def with_asset_names(html: str) -> str:
    if 'id="asset-names-script"' in html:
        return html
    return html.replace("</head>", '<style id="asset-names-style">'
                        'table:has(.asset-name){table-layout:auto}'
                        'div:has(>table .asset-name){overflow-x:auto}'
                        'td.asset-name,th.asset-name{min-width:170px;max-width:300px;white-space:normal;'
                        'overflow-wrap:break-word;text-align:left;line-height:1.4}'
                        '.asset-name-caption{display:block;max-width:220px;white-space:normal;'
                        'font-size:11px;font-weight:400;line-height:1.4;color:var(--muted,#65748a)}'
                        '</style><script id="asset-names-script">' + asset_names_javascript() + '</script></head>', 1)


_JAVASCRIPT = r"""
const AssetNames = (() => {
  const names = Object.freeze(__ASSET_NAMES__);
  const key = symbol => String(symbol ?? '').trim().toUpperCase();
  const escape = value => String(value).replace(/[&<>"']/g,
    c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const name = (symbol, supplied) => String(supplied || '').trim() ||
    (Object.hasOwn(names, key(symbol)) ? names[key(symbol)] : key(symbol) ? 'Name unavailable' : '—');
  const label = (symbol, supplied) => key(symbol) === 'CASH' ? 'Cash' : `${symbol ?? ''} · ${name(symbol, supplied)}`;
  const cell = (symbol, supplied) => `<td class="asset-name">${escape(name(symbol, supplied))}</td>`;
  return Object.freeze({name, label, cell});
})();
"""
