from __future__ import annotations

from functools import lru_cache

from systematic_trading.presentation.templates import load_template

from systematic_trading.chart_navigation import with_chart_navigation
from systematic_trading.web.shell import with_app_shell
from systematic_trading.web.backup_panel import BACKUP_PANEL_HTML
from systematic_trading.storage.backup_status import backup_status
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse

router = APIRouter()
REPO_ROOT = Path(__file__).resolve().parents[3]


@router.get("/api/v1/platform/backups")
def platform_backups() -> JSONResponse:
    return JSONResponse(backup_status(REPO_ROOT), headers={"Cache-Control": "no-store"})


@router.get("/platform", response_class=HTMLResponse, include_in_schema=False)
def platform_health_portal() -> HTMLResponse:
    return HTMLResponse(_platform_health_portal_html())


@lru_cache(maxsize=1)
def _platform_health_portal_html() -> str:
    page = _PLATFORM_HTML.replace(
        '    <div class="layout">', BACKUP_PANEL_HTML + '\n    <div class="layout">', 1
    )
    return with_app_shell(page, "system")


@router.get(
    "/platform/market-data-audit", response_class=HTMLResponse, include_in_schema=False
)
def market_data_audit_portal() -> HTMLResponse:
    return HTMLResponse(_market_data_audit_portal_html())


@lru_cache(maxsize=1)
def _market_data_audit_portal_html() -> str:
    from systematic_trading.web.research_archive_panel import RESEARCH_ARCHIVE_HTML
    from systematic_trading.web.governed_panel import GOVERNED_HTML
    from systematic_trading.web.economic_panel import ECONOMIC_HTML
    from systematic_trading.web.positioning_panel import POSITIONING_HTML
    from systematic_trading.web.energy_panel import ENERGY_HTML
    from systematic_trading.web.issuer_panel import ISSUER_HTML
    from systematic_trading.web.market_history_ui import MARKET_HISTORY_UI_HTML

    page = _MARKET_DATA_AUDIT_HTML.replace(
        "<main>",
        '<main><section id="market-history-section" aria-label="Market History">'
        + MARKET_HISTORY_UI_HTML
        + RESEARCH_ARCHIVE_HTML
        + GOVERNED_HTML
        + ECONOMIC_HTML
        + POSITIONING_HTML
        + ENERGY_HTML
        + ISSUER_HTML
        + '<div id="market-bars-panel" data-market-view="bars" hidden>',
        1,
    )
    page = page.replace("<body>", '<body class="market-data-page">', 1)
    return with_app_shell(
        with_chart_navigation(page.replace("</main>", "</div></section></main>", 1)),
        "market",
    )


_PLATFORM_HTML = load_template("web/platform_platform.html")


_MARKET_DATA_AUDIT_HTML = load_template("web/platform_market_data_audit.html")
