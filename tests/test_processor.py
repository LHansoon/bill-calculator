"""Characterization tests for Processor.process (G0.4).

result[debtor][creditor] = amount debtor owes creditor, before netting.
Assertions pin CURRENT behavior, not an ideal one.
"""
import pytest

import Processor
from Content import Content

TAX = 0.15


def _process(records):
    return Processor.Processor().process(Content(records), TAX)


def _buy(who, payer="bob", price=10, tax_flg=""):
    return {"date": "2025-04-01", "category": "grocery", "from": payer,
            "to": "Store", "product": "x", "price": price,
            "tax_flg": tax_flg, "who": who, "tag": "", "type": "buy"}


def test_even_split_payer_does_not_owe_self():
    result, _, _ = _process([_buy("alice,bob")])
    assert result == {"alice": {"bob": 5.0}}


def test_weighted_shares_full_width():
    result, _, _ = _process([_buy("alice（2），bob（1）", price=30)])
    assert result == {"alice": {"bob": 20.0}}


def test_tax_flag_applies_tax_rate():
    result, _, _ = _process([_buy("carol", payer="alice", price=100,
                                  tax_flg="y")])
    assert result["carol"]["alice"] == pytest.approx(115.0)


def test_full_sample_matrix(sample_records):
    result, user_stat, missing = _process(sample_records)
    # buy rows: bob owes alice 5, alice owes bob 20, carol owes alice 115
    # pay bob->alice 5:      result[alice][bob] += 5            -> 25
    # debt_trans bob->alice about carol, 2:
    #     result[bob][alice] -= 2 -> 3; result[carol][alice] += 2;
    #     result[carol][bob] -= 2 -> -2
    # debt_adj carol->alice 1: result[carol][alice] += 1         -> 118
    assert result == {
        "bob": {"alice": 3.0},
        "alice": {"bob": 25.0},
        "carol": {"alice": 118.0, "bob": -2.0},
    }
    # one user_stat row per sharer of each valid buy row
    assert len(user_stat) == 2 + 2 + 1


def test_missing_from_reported_by_sheet_line(sample_records):
    _, _, missing = _process(sample_records)
    # row index 6 -> sheet line 8 (1-based, plus header row)
    assert missing == {8: ["from"]}


def test_bad_share_defaults_to_one_instead_of_crashing(caplog):
    # "(x)" matches the share regex but is not a number
    with caplog.at_level("WARNING", logger="Processor"):
        result, _, _ = _process([_buy("alice(x),bob")])
    assert result == {"alice": {"bob": 5.0}}
    assert "cannot parse share" in caplog.text


def test_summary_drops_users_with_zero_past_30_days(sample_records):
    # all sample dates are in 2025, far outside the last 30 days
    _, user_stat, _ = _process(sample_records)
    *_, past_30_days = Processor.get_summary(user_stat)
    assert past_30_days == {}
