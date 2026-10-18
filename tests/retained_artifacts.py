"""Distinguish intentionally retired replay outputs from unexplained data loss."""
from functools import wraps
from pathlib import Path

import pytest

from systematic_trading.storage.artifact_retention import retirement_for_path


def requires_artifact(path):
    def decorate(function):
        @wraps(function)
        def run(*args, **kwargs):
            if not Path(path).exists():
                receipt=retirement_for_path(Path('var'),path)
                if receipt:
                    pytest.skip('Exact historical replay retired under '+receipt['manifest_sha256'])
                raise AssertionError('Historical artifact missing without retirement evidence: '+str(path))
            return function(*args, **kwargs)
        return run
    return decorate
