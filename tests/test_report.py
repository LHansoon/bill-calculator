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
