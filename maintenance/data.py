"""Synthetic pre-failure sensor events and causal rolling features."""
from collections import deque
import numpy as np
import pandas as pd

FEATURES = ['temperature', 'vibration', 'pressure', 'load', 'supplier_fault_rate',
            'temperature_mean_6h', 'vibration_mean_6h', 'vibration_trend_6h', 'pressure_delta_6h']


def features(history):
    """Use only current/past sensor events. No failure time, label or asset identity."""
    h = list(history)[-6:]
    r = h[-1]
    dt = max((r['timestamp'] - h[0]['timestamp']) / 3600, 1)
    return [r['temperature'], r['vibration'], r['pressure'], r['load'], r['supplier_fault_rate'],
            float(np.mean([e['temperature'] for e in h])),
            float(np.mean([e['vibration'] for e in h])),
            (r['vibration'] - h[0]['vibration']) / dt,
            r['pressure'] - h[0]['pressure']]


def generate(n_assets=120, seed=42, prefix='asset'):
    """Illustrative hourly pump-like telemetry, not a physical degradation model.

    Supplier rates represent a synthetic prior history available before observation.
    Future failure times create labels only; features never receive them.
    """
    rng = np.random.default_rng(seed)
    events, rows = [], []
    for asset in range(n_assets):
        prior = float(rng.choice([.04, .12, .28]))
        failure_hour = int(rng.integers(48, 105) - 15 * prior)
        baseline = rng.normal(0, .8)
        history = deque(maxlen=6)
        for hour in range(min(failure_hour, 72)):
            wear = max(0, (hour - (failure_hour - 30)) / 30)
            load = float(np.clip(rng.normal(.65, .15), .1, 1))
            e = {'event_id': f'{prefix}-{asset:03d}-{hour:03d}', 'asset_id': f'{prefix}-{asset:03d}',
                 'timestamp': 1767225600 + hour * 3600,
                 'temperature': float(55 + baseline + 12 * wear + 8 * load + rng.normal(0, 2.5)),
                 'vibration': float(max(.05, 1.2 + 2.6 * wear + .5 * load + rng.normal(0, .5))),
                 'pressure': float(7 - 1.7 * wear + rng.normal(0, .35)),
                 'load': load, 'supplier_fault_rate': prior}
            history.append(e)
            events.append(e)
            row = dict(zip(FEATURES, features(history)))
            row.update(asset_id=e['asset_id'], event_id=e['event_id'], timestamp=e['timestamp'],
                       failure_in_12h=int(0 < failure_hour-hour <= 12))
            rows.append(row)
    return events, pd.DataFrame(rows)
