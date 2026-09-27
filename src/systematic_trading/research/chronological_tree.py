"""Research-only dated model selection; no fallback to a future fitted tree."""
from systematic_trading.research.rolling_models import load_model, window_start


def select_base_tree(schedule, known_through):
    eligible = [d for d in schedule if d <= known_through]
    if not eligible:
        raise ValueError('No historical base tree available before this decision')
    fit = max(eligible)
    item = schedule[fit]
    if item['fit_as_of'] != fit or item['max_label_end'] >= fit or item['max_feature_date'] >= fit:
        raise ValueError('Base tree contains future labels or features')
    if item['training_samples'] < 100:
        raise ValueError('Insufficient chronological base-tree training samples')
    if item.get('window_years') is not None:
        years = item['window_years']
        if years not in (1, 2) or item['window_start'] != window_start(fit, years):
            raise ValueError('Invalid rolling model window')
        if not item['window_start'] <= item['min_feature_date'] <= item['max_feature_date'] < fit:
            raise ValueError('Training origin outside the rolling model window')
    return load_model(item['model'])
