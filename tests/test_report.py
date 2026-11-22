import pytest

import Processor
from Content import Content
from datetime import date


@pytest.fixture
def user_stat(sample_records):
    content = Content(sample_records)
    _, user_stat, _ = Processor.Processor().process(content, 0.15)
    return user_stat


def test_february_window_only_counts_february(user_stat):
    report = Processor.get_user_report(
        user_stat, date(2025, 2, 1), date(2025, 2, 28))
    assert report["bob"]["total_purchase"] == {"dining": 30.0}
    assert report["bob"]["self_purchase"] == {"dining": 10.0}
    assert report["bob"]["others_purchase"] == {"dining": 20.0}
    assert report["alice"]["total_expenditure"] == {"dining": 20.0}
    assert report["alice"]["total_purchase"] == {}
    assert "carol" not in report


def test_total_equals_self_plus_others(user_stat):
    report = Processor.get_user_report(
        user_stat, date(2025, 1, 1), date(2025, 12, 31))
    for user, sections in report.items():
        for category, total in sections["total_purchase"].items():
            self_v = sections["self_purchase"].get(category, 0)
            other_v = sections["others_purchase"].get(category, 0)
            assert total == pytest.approx(self_v + other_v, abs=0.01)


def test_transactions_range_is_inclusive_and_newest_first(user_stat):
    rows = Processor.get_transactions(
        user_stat, date(2025, 1, 15), date(2025, 2, 10))
    # Jan 15 eggs split alice/bob, Feb 10 chicken split alice/bob
    assert [r["date"] for r in rows] == [
        "2025-02-10", "2025-02-10", "2025-01-15", "2025-01-15"]


def test_transactions_fields_and_rounding(user_stat):
    rows = Processor.get_transactions(
        user_stat, date(2025, 3, 5), date(2025, 3, 5))
    assert rows == [{
        "date": "2025-03-05", "paid_by": "alice", "user": "carol",
        "merchant": "BestBuy", "category": "electronics",
        "event_tag": "", "amount": 115.0,
    }]


def test_transactions_amounts_are_two_decimals(user_stat):
    rows = Processor.get_transactions(
        user_stat, date(2025, 2, 10), date(2025, 2, 10))
    assert sorted(r["amount"] for r in rows) == [10.0, 20.0]
    for r in rows:
        assert r["amount"] == round(r["amount"], 2)


def test_transactions_empty_range(user_stat):
    assert Processor.get_transactions(
        user_stat, date(2030, 1, 1), date(2030, 12, 31)) == []
