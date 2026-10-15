from __future__ import annotations

from functools import lru_cache

from systematic_trading.presentation.templates import load_template

from systematic_trading.chart_navigation import with_chart_navigation
from systematic_trading.web.shell import with_app_shell

from systematic_trading.web.trading_workspace import (
    WORKSPACE_CSS,
    WORKSPACE_HTML,
    WORKSPACE_DIALOG,
    WORKSPACE_JS,
)

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse

router = APIRouter()


@router.get("/", include_in_schema=False)
def root_redirect() -> RedirectResponse:
    return RedirectResponse(url="/operator")


@router.get("/operator", response_class=HTMLResponse, include_in_schema=False)
def operator_dashboard() -> HTMLResponse:
    return HTMLResponse(_operator_dashboard_html())


@lru_cache(maxsize=1)
def _operator_dashboard_html() -> str:
    html = _OPERATOR_HTML.replace("</style>", WORKSPACE_CSS + "</style>", 1)
    from systematic_trading.web.signal_decay_ui import ALERT_HTML, ALERT_JS

    html = html.replace("<main>", "<main>" + ALERT_HTML + WORKSPACE_HTML, 1)
    html = html.replace("<script>", ALERT_JS + "<script>", 1)
    html = html.replace("<script>", WORKSPACE_DIALOG + "<script>", 1)
    html = html.replace(
        "    Promise.all([loadProposals(), loadDashboardData()])",
        WORKSPACE_JS + "\n    Promise.all([loadProposals(), loadDashboardData()])",
        1,
    )
    return with_app_shell(with_chart_navigation(html), "trading")


@router.get("/strategies", response_class=HTMLResponse, include_in_schema=False)
def strategy_portal() -> HTMLResponse:
    return HTMLResponse(_strategy_portal_html())


@lru_cache(maxsize=1)
def _strategy_portal_html() -> str:
    from systematic_trading.web.strategy_lifecycle_ui import HTML, JS
    from systematic_trading.web.signal_decay_ui import (
        HTML as DECAY_HTML,
        JS as DECAY_JS,
    )

    html = _STRATEGIES_HTML.replace("<script>", HTML + "<script>" + JS, 1)
    # Placed at the top of the workspace: signal health is the first thing an
    # operator should see before acting on any strategy row below it.
    html = html.replace("<main>", "<main>" + DECAY_HTML, 1)
    html = html.replace("<script>", "<script>" + DECAY_JS, 1)
    return with_app_shell(html, "strategies")


@router.get(
    "/strategies/{strategy_id}", response_class=HTMLResponse, include_in_schema=False
)
def strategy_detail_portal(strategy_id: str) -> HTMLResponse:
    return HTMLResponse(_strategy_detail_portal_html())


@lru_cache(maxsize=1)
def _strategy_detail_portal_html() -> str:
    html = _STRATEGY_DETAIL_HTML.replace("join('\n')", "join(String.fromCharCode(10))")
    return with_app_shell(with_chart_navigation(html), "strategies")


_OPERATOR_HTML = load_template("web/operator_operator.html")


_STRATEGIES_HTML = load_template("web/operator_strategies.html")


_STRATEGY_DETAIL_HTML = load_template("web/operator_strategy_detail.html")
