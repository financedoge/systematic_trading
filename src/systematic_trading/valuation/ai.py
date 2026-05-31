from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Any, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from systematic_trading.valuation.framework import StockFrameworkScreen


DEFAULT_OPENAI_MODEL = "gpt-5"


class OpenAIStockScreenError(RuntimeError):
    pass


class OpenAIStockFrameworkClient:
    endpoint = "https://api.openai.com/v1/responses"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        api_key_path: Path | None = None,
        model: str | None = None,
        timeout_seconds: int = 180,
    ) -> None:
        self.api_key = api_key or _load_api_key(api_key_path)
        self.model = model or os.getenv("ST_OPENAI_MODEL") or DEFAULT_OPENAI_MODEL
        self.timeout_seconds = timeout_seconds
        if not self.api_key:
            raise OpenAIStockScreenError("OpenAI API key was not found in OPENAI_API_KEY or ./openai_key.txt.")

    def score_candidates(
        self,
        *,
        as_of: date,
        universe_name: str,
        candidates: Sequence[dict[str, object]],
        use_web_search: bool = True,
        reasoning_effort: str | None = "low",
    ) -> StockFrameworkScreen:
        payload: dict[str, Any] = {
            "model": self.model,
            "instructions": _instructions(as_of=as_of),
            "input": _input_payload(
                as_of=as_of,
                universe_name=universe_name,
                candidates=candidates,
                use_web_search=use_web_search,
            ),
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "stock_framework_screen",
                    "strict": True,
                    "schema": _screen_schema(),
                }
            },
            "max_output_tokens": 16000,
        }
        if reasoning_effort:
            payload["reasoning"] = {"effort": reasoning_effort}
        if use_web_search:
            payload["tools"] = [
                {
                    "type": "web_search",
                    "user_location": {
                        "type": "approximate",
                        "country": "US",
                        "timezone": "America/New_York",
                    },
                }
            ]
            payload["tool_choice"] = "auto"
            payload["include"] = ["web_search_call.action.sources"]

        response = self._post(payload)
        text = _extract_output_text(response)
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise OpenAIStockScreenError(f"OpenAI returned non-JSON stock screen output: {exc}") from exc
        data["model"] = str(data.get("model") or self.model)
        return StockFrameworkScreen.model_validate(data)

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise OpenAIStockScreenError(f"OpenAI API request failed with HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise OpenAIStockScreenError(f"OpenAI API request failed: {exc}") from exc


def _load_api_key(api_key_path: Path | None) -> str | None:
    env_key = os.getenv("OPENAI_API_KEY")
    if env_key:
        return env_key.strip()
    path = api_key_path or Path("openai_key.txt")
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8").strip()


def _instructions(*, as_of: date) -> str:
    return (
        "You are a research assistant implementing a probability-based stock valuation screen. "
        "Score candidates for research prioritization only; do not issue production buy/sell advice. "
        "Use current public evidence when web search is enabled, and cite URLs in source_urls. "
        f"The analysis date is {as_of.isoformat()}. "
        "Return only JSON matching the supplied schema."
    )


def _input_payload(
    *,
    as_of: date,
    universe_name: str,
    candidates: Sequence[dict[str, object]],
    use_web_search: bool,
) -> str:
    framework = {
        "scorecard": {
            "valuation_dislocation": 25,
            "recovery_potential": 20,
            "business_quality": 15,
            "balance_sheet": 15,
            "earnings_revision": 10,
            "macro_scenario_skew": 10,
            "regime_change_optionality": 5,
        },
        "preferred_opportunity_hierarchy": [
            "major_regime_change",
            "fallen_angel",
            "deep_value_recovery",
            "cyclical_macro",
            "quality_first_value",
            "defensive_compounder",
        ],
        "behavioral_overlay": {
            "sector_thematic_beta": 5,
            "narrative_strength": 5,
            "retail_sentiment": 5,
            "options_technical_momentum": 3,
            "positioning_asymmetry": 2,
        },
        "rating_map": {
            "A": "High-conviction compounder at attractive/reasonable price",
            "B": "Mispriced recovery or fallen angel with credible path",
            "C": "Cyclical value with favorable risk/reward and macro skew",
            "D": "Cheap but low quality; watchlist only",
            "E": "Avoid/value-trap/insufficient upside for risk",
        },
    }
    task = {
        "as_of": as_of.isoformat(),
        "universe": universe_name,
        "web_search_enabled": use_web_search,
        "instructions": [
            "Score every candidate using the framework.",
            "Estimate probability-weighted fair value and scenario values; use ranges conservatively if precise data is unavailable.",
            "Prefer fallen angels, deep-value recovery, cyclical macro, and durable regime-change names, but penalize value traps and balance-sheet risk.",
            "Use the supplied market features as price-path context; they are not sufficient by themselves.",
            "source_urls should contain the most relevant URLs used for each stock; leave empty only if no web evidence was available.",
            "Keep key_thesis and main_risk to one concise sentence each.",
        ],
        "framework": framework,
        "candidates": list(candidates),
    }
    return json.dumps(task, separators=(",", ":"), ensure_ascii=False)


def _extract_output_text(response: dict[str, Any]) -> str:
    if isinstance(response.get("output_text"), str):
        return str(response["output_text"])
    chunks: list[str] = []
    for item in response.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                chunks.append(content["text"])
    if chunks:
        return "".join(chunks)
    raise OpenAIStockScreenError("OpenAI response did not contain output_text.")


def _screen_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["as_of", "framework_version", "model", "universe", "reports", "notes"],
        "properties": {
            "as_of": {"type": "string", "format": "date"},
            "framework_version": {"type": "string"},
            "model": {"type": "string"},
            "universe": {"type": "string"},
            "reports": {"type": "array", "items": _report_schema()},
            "notes": {"type": "array", "items": {"type": "string"}},
        },
    }


def _report_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "ticker",
            "company",
            "market",
            "sector",
            "as_of",
            "opportunity_bucket",
            "total_score",
            "score_breakdown",
            "behavioral_overlay_score",
            "current_price",
            "probability_weighted_fair_value",
            "expected_upside",
            "bear_case_downside",
            "quality_score",
            "positive_thesis_probability",
            "final_rating",
            "key_thesis",
            "main_risk",
            "deep_dive_priority",
            "scenarios",
            "source_urls",
            "review_notes",
        ],
        "properties": {
            "ticker": {"type": "string"},
            "company": {"type": "string"},
            "market": {"type": "string"},
            "sector": {"type": "string"},
            "as_of": {"type": "string", "format": "date"},
            "opportunity_bucket": {
                "type": "string",
                "enum": [
                    "major_regime_change",
                    "fallen_angel",
                    "deep_value_recovery",
                    "cyclical_macro",
                    "quality_first_value",
                    "defensive_compounder",
                ],
            },
            "total_score": {"type": "number", "minimum": 0, "maximum": 100},
            "score_breakdown": _score_breakdown_schema(),
            "behavioral_overlay_score": _behavioral_schema(),
            "current_price": {"type": "number", "exclusiveMinimum": 0},
            "probability_weighted_fair_value": {"type": "number", "minimum": 0},
            "expected_upside": {"type": "number"},
            "bear_case_downside": {"type": "number"},
            "quality_score": {"type": "number", "minimum": 0, "maximum": 100},
            "positive_thesis_probability": {"type": "number", "minimum": 0, "maximum": 1},
            "final_rating": {"type": "string", "enum": ["A", "B", "C", "D", "E"]},
            "key_thesis": {"type": "string"},
            "main_risk": {"type": "string"},
            "deep_dive_priority": {"type": "string", "enum": ["high", "medium", "low"]},
            "scenarios": {
                "type": "array",
                "minItems": 4,
                "items": _scenario_schema(),
            },
            "source_urls": {"type": "array", "items": {"type": "string"}},
            "review_notes": {"type": "array", "items": {"type": "string"}},
        },
    }


def _score_breakdown_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "valuation_dislocation",
            "recovery_potential",
            "business_quality",
            "balance_sheet",
            "earnings_revision",
            "macro_scenario_skew",
            "regime_change_optionality",
            "penalties",
        ],
        "properties": {
            "valuation_dislocation": {"type": "number", "minimum": 0, "maximum": 25},
            "recovery_potential": {"type": "number", "minimum": 0, "maximum": 20},
            "business_quality": {"type": "number", "minimum": 0, "maximum": 15},
            "balance_sheet": {"type": "number", "minimum": 0, "maximum": 15},
            "earnings_revision": {"type": "number", "minimum": 0, "maximum": 10},
            "macro_scenario_skew": {"type": "number", "minimum": 0, "maximum": 10},
            "regime_change_optionality": {"type": "number", "minimum": 0, "maximum": 5},
            "penalties": {"type": "number", "minimum": -50, "maximum": 0},
        },
    }


def _behavioral_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "sector_thematic_beta",
            "narrative_strength",
            "retail_sentiment",
            "options_technical_momentum",
            "positioning_asymmetry",
        ],
        "properties": {
            "sector_thematic_beta": {"type": "number", "minimum": 0, "maximum": 5},
            "narrative_strength": {"type": "number", "minimum": 0, "maximum": 5},
            "retail_sentiment": {"type": "number", "minimum": 0, "maximum": 5},
            "options_technical_momentum": {"type": "number", "minimum": 0, "maximum": 3},
            "positioning_asymmetry": {"type": "number", "minimum": 0, "maximum": 2},
        },
    }


def _scenario_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["name", "probability", "fair_value", "implied_upside", "key_assumption"],
        "properties": {
            "name": {"type": "string"},
            "probability": {"type": "number", "minimum": 0, "maximum": 1},
            "fair_value": {"type": "number", "minimum": 0},
            "implied_upside": {"type": "number"},
            "key_assumption": {"type": "string"},
        },
    }
