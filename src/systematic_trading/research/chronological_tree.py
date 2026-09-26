"""Research-only dated model selection; no fallback to a future fitted tree."""
from systematic_trading.signals.decision_tree import SimpleDecisionTreeModel


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
    return SimpleDecisionTreeModel.from_dict(item['model'])
