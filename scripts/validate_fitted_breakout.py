"""Three independent native checks for the fitted signal's incremental portfolios."""
import json
from types import SimpleNamespace

import fit_breakout_signal_audit as study
import run_fitted_breakout_portfolios as portfolio
from validate_breakout_revisit import validate_study


def main():
    portfolio.read_signals()
    evidence = json.loads((study.OUTPUT / "portfolio-results.json").read_text())
    if evidence["script_sha256"] != study.digest(study.Path(portfolio.__file__)):
        raise ValueError("Portfolio runner changed")
    facade = SimpleNamespace(**{k: getattr(study, k) for k in ("ROOT", "WORK", "OUTPUT", "protocol", "digest", "write", "frozen")},
                             PRIMARY=portfolio.PRIMARY)
    validate_study(facade, "portfolio-results.json", "selection_dynamic")


if __name__ == "__main__":
    main()
