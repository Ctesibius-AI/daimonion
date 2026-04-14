"""
Usage Tracker — Log every API call with model, tokens, cost, component, duration.

Daily JSON files at ~/.daimonion/usage/YYYY-MM-DD.json.
"""

import json
import os
import time
from datetime import datetime, timezone

from src.config import USAGE_DIR

PRICING = {
    'claude-haiku-4-5-20251001': {'input': 0.80, 'cached_input': 0.08, 'output': 4.00},
    'claude-sonnet-4-6': {'input': 3.00, 'cached_input': 0.30, 'output': 15.00},
    'claude-opus-4-6': {'input': 15.00, 'cached_input': 1.50, 'output': 75.00},
}

BRAVE_COST_PER_SEARCH = 0.005


class UsageTracker:

    def __init__(self):
        self._today = None
        self._data = None

    def _today_path(self) -> str:
        return os.path.join(USAGE_DIR, f'{datetime.now(timezone.utc).strftime("%Y-%m-%d")}.json')

    def _load(self) -> dict:
        date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        if self._today == date and self._data:
            return self._data

        path = self._today_path()
        if os.path.exists(path):
            try:
                with open(path) as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._data = self._empty(date)
        else:
            self._data = self._empty(date)

        self._today = date
        return self._data

    def _save(self):
        if not self._data:
            return
        tmp = self._today_path() + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(self._data, f, indent=2)
        os.replace(tmp, self._today_path())

    def _empty(self, date: str) -> dict:
        return {
            'date': date, 'total_cost_usd': 0.0,
            'total_input_tokens': 0, 'total_output_tokens': 0, 'total_cached_tokens': 0,
            'total_calls': 0, 'calls_by_model': {}, 'calls_by_component': {},
            'brave_searches': 0, 'brave_cost_usd': 0.0, 'calls': [],
        }

    def _cost(self, model: str, input_t: int, output_t: int, cached_t: int = 0) -> float:
        r = PRICING.get(model, {'input': 3.0, 'cached_input': 0.30, 'output': 15.0})
        return round(((input_t - cached_t) * r['input'] + cached_t * r['cached_input'] + output_t * r['output']) / 1e6, 6)

    def log(self, response, component: str, duration_ms: int = 0) -> float:
        """Log an Anthropic API response."""
        data = self._load()
        model = getattr(response, 'model', 'unknown')
        inp = response.usage.input_tokens
        out = response.usage.output_tokens
        cached = getattr(response.usage, 'cache_read_input_tokens', 0)
        cost = self._cost(model, inp, out, cached)

        data['calls'].append({
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'model': model, 'component': component,
            'input_tokens': inp, 'output_tokens': out,
            'cached_input_tokens': cached, 'cost_usd': cost, 'duration_ms': duration_ms,
        })
        data['total_cost_usd'] = round(data['total_cost_usd'] + cost, 6)
        data['total_input_tokens'] += inp
        data['total_output_tokens'] += out
        data['total_cached_tokens'] += cached
        data['total_calls'] += 1

        data['calls_by_model'].setdefault(model, {'calls': 0, 'cost_usd': 0.0})
        data['calls_by_model'][model]['calls'] += 1
        data['calls_by_model'][model]['cost_usd'] = round(data['calls_by_model'][model]['cost_usd'] + cost, 6)

        data['calls_by_component'].setdefault(component, {'calls': 0, 'cost_usd': 0.0})
        data['calls_by_component'][component]['calls'] += 1
        data['calls_by_component'][component]['cost_usd'] = round(data['calls_by_component'][component]['cost_usd'] + cost, 6)

        self._save()
        return cost

    def log_brave(self, query: str, result_count: int = 0):
        data = self._load()
        data['brave_searches'] += 1
        data['brave_cost_usd'] = round(data['brave_cost_usd'] + BRAVE_COST_PER_SEARCH, 6)
        data['total_cost_usd'] = round(data['total_cost_usd'] + BRAVE_COST_PER_SEARCH, 6)
        self._save()

    def get_today_summary(self) -> dict:
        data = self._load()
        return {'date': data['date'], 'total_cost_usd': data['total_cost_usd'],
                'total_calls': data['total_calls'], 'calls_by_model': data['calls_by_model']}

    def get_month_to_date(self) -> dict:
        prefix = datetime.now(timezone.utc).strftime('%Y-%m')
        total_cost = 0.0
        total_calls = 0
        days = 0
        for fname in os.listdir(USAGE_DIR):
            if fname.startswith(prefix) and fname.endswith('.json'):
                try:
                    with open(os.path.join(USAGE_DIR, fname)) as f:
                        d = json.load(f)
                    total_cost += d.get('total_cost_usd', 0)
                    total_calls += d.get('total_calls', 0)
                    days += 1
                except (json.JSONDecodeError, IOError):
                    continue
        daily_avg = total_cost / max(days, 1)
        return {
            'month': prefix, 'total_cost_usd': round(total_cost, 4),
            'total_calls': total_calls, 'days': days,
            'projected_monthly_usd': round(daily_avg * 30, 2),
        }


tracker = UsageTracker()
