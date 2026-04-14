"""
Unit tests for the API usage tracker.

Tests daily logging, cost calculation, month-to-date aggregation.
"""

import json
import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.tools.usage_tracker import UsageTracker, PRICING


@pytest.fixture
def tracker(tmp_path):
    with patch('src.tools.usage_tracker.USAGE_DIR', str(tmp_path)):
        t = UsageTracker()
        yield t


def _mock_response(model='claude-sonnet-4-6', input_tokens=100, output_tokens=50,
                   cache_read=0):
    resp = MagicMock()
    resp.model = model
    resp.usage = MagicMock()
    resp.usage.input_tokens = input_tokens
    resp.usage.output_tokens = output_tokens
    resp.usage.cache_read_input_tokens = cache_read
    return resp


class TestCostCalculation:
    def test_sonnet_cost(self, tracker):
        resp = _mock_response(model='claude-sonnet-4-6',
                              input_tokens=1000, output_tokens=500)
        cost = tracker.log(resp, 'test')
        # (1000 * 3.0 + 500 * 15.0) / 1e6
        expected = (1000 * 3.0 + 500 * 15.0) / 1e6
        assert cost == pytest.approx(expected, abs=0.0001)

    def test_haiku_cost(self, tracker):
        resp = _mock_response(model='claude-haiku-4-5-20251001',
                              input_tokens=1000, output_tokens=500)
        cost = tracker.log(resp, 'test')
        expected = (1000 * 0.80 + 500 * 4.00) / 1e6
        assert cost == pytest.approx(expected, abs=0.0001)

    def test_opus_cost(self, tracker):
        resp = _mock_response(model='claude-opus-4-6',
                              input_tokens=1000, output_tokens=500)
        cost = tracker.log(resp, 'test')
        expected = (1000 * 15.0 + 500 * 75.0) / 1e6
        assert cost == pytest.approx(expected, abs=0.0001)

    def test_cached_input_discount(self, tracker):
        resp = _mock_response(model='claude-sonnet-4-6',
                              input_tokens=1000, output_tokens=100, cache_read=800)
        cost = tracker.log(resp, 'test')
        # (200 * 3.0 + 800 * 0.30 + 100 * 15.0) / 1e6
        expected = (200 * 3.0 + 800 * 0.30 + 100 * 15.0) / 1e6
        assert cost == pytest.approx(expected, abs=0.0001)


class TestDailyTracking:
    def test_logs_call(self, tracker):
        resp = _mock_response()
        tracker.log(resp, 'daytime.sonnet')
        summary = tracker.get_today_summary()
        assert summary['total_calls'] == 1
        assert summary['total_cost_usd'] > 0

    def test_multiple_calls_accumulate(self, tracker):
        for _ in range(3):
            tracker.log(_mock_response(), 'test')
        assert tracker.get_today_summary()['total_calls'] == 3

    def test_calls_by_model(self, tracker):
        tracker.log(_mock_response(model='claude-sonnet-4-6'), 'test')
        tracker.log(_mock_response(model='claude-opus-4-6'), 'test')
        summary = tracker.get_today_summary()
        assert 'claude-sonnet-4-6' in summary['calls_by_model']
        assert 'claude-opus-4-6' in summary['calls_by_model']

    def test_brave_search_tracked(self, tracker):
        tracker.log_brave('test query', 5)
        data = tracker._load()
        assert data['brave_searches'] == 1
        assert data['brave_cost_usd'] > 0

    def test_persists_to_disk(self, tracker, tmp_path):
        tracker.log(_mock_response(), 'test')
        # Load fresh
        files = [f for f in os.listdir(tmp_path) if f.endswith('.json')]
        assert len(files) == 1
        with open(os.path.join(tmp_path, files[0])) as f:
            data = json.load(f)
        assert data['total_calls'] == 1


class TestMonthToDate:
    def test_aggregates_daily_files(self, tracker, tmp_path):
        # Create fake daily files
        prefix = datetime.now(timezone.utc).strftime('%Y-%m')
        for day in range(1, 4):
            data = {
                'date': f'{prefix}-{day:02d}',
                'total_cost_usd': 0.5,
                'total_calls': 10,
            }
            with open(os.path.join(tmp_path, f'{prefix}-{day:02d}.json'), 'w') as f:
                json.dump(data, f)

        with patch('src.tools.usage_tracker.USAGE_DIR', str(tmp_path)):
            t = UsageTracker()
            mtd = t.get_month_to_date()
        assert mtd['total_cost_usd'] == pytest.approx(1.5, abs=0.01)
        assert mtd['total_calls'] == 30
        assert mtd['days'] == 3


class TestAllModelsHavePricing:
    @pytest.mark.parametrize('model', PRICING.keys())
    def test_pricing_has_all_fields(self, model):
        p = PRICING[model]
        assert 'input' in p
        assert 'cached_input' in p
        assert 'output' in p
        assert p['cached_input'] < p['input']
