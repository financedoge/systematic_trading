"""Load immutable, packaged UTF-8 templates without depending on the web app."""

from functools import lru_cache
from importlib.resources import files


@lru_cache(maxsize=32)
def load_template(name: str) -> str:
    if (
        not name
        or ":" in name
        or any(part in ("", ".", "..") for part in name.split("/"))
        or "\\" in name
    ):
        raise ValueError("Expected a relative template resource name")
    return (
        files("systematic_trading.presentation")
        .joinpath("assets", name)
        .read_text(encoding="utf-8")
    )
