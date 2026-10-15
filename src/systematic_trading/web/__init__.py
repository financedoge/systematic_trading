"""Web adapters. Importing a presentation helper does not initialize API routes."""

__all__ = ["router"]


def __getattr__(name: str):
    if name == "router":
        from systematic_trading.web.api import router

        return router
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
