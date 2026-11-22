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
    assert missing == {8: ["missing from"]}


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


# ---- regression tests for the calculation bugs found in #112 ----

def _row(who="", payer="alice", price=30, tax_flg="", typ="buy",
         to="Store", date="2025-04-01"):
    return {"date": date, "category": "c", "from": payer, "to": to,
            "product": "x", "price": price, "tax_flg": tax_flg,
            "who": who, "tag": "", "type": typ}


def test_payer_with_trailing_space_still_counts():
    result, user_stat, missing = _process([_row("bob,carol", payer="alice ")])
    assert result == {"bob": {"alice": 15.0}, "carol": {"alice": 15.0}}
    assert set(user_stat["paid_by"]) == {"alice"}
    assert missing == {}


@pytest.mark.parametrize("who", ["alice,bob,carol,", "alice, ,bob,carol",
                                 " ,alice,bob,carol"])
def test_blank_names_in_who_are_ignored(who):
    result, _, missing = _process([_row(who)])
    assert result == {"bob": {"alice": 10.0}, "carol": {"alice": 10.0}}
    assert missing == {}


@pytest.mark.parametrize("who", ["alice,bob,bob", "alice(1),bob(1),bob(1)"])
def test_repeated_name_adds_shares(who):
    result, _, _ = _process([_row(who)])
    assert result == {"bob": {"alice": 20.0}}


def test_zero_shares_reported_not_crashing():
    result, _, missing = _process([_row("bob(0),carol(0)")])
    assert result == {}
    assert "no positive shares" in missing[2][0]


@pytest.mark.parametrize("flag,expected", [("Y", 34.5), ("y", 34.5),
                                           ("n", 30.0), ("N", 30.0),
                                           ("", 30.0), (0.1, 33.0)])
def test_tax_flag_variants(flag, expected):
    result, _, missing = _process([_row("bob", tax_flg=flag)])
    assert result["bob"]["alice"] == pytest.approx(expected)
    assert missing == {}


def test_unknown_tax_flag_reported():
    result, _, missing = _process([_row("bob", tax_flg="maybe")])
    assert result == {}
    assert "tax_flg 'maybe'" in missing[2][0]


@pytest.mark.parametrize("typ", ["buy", "pay", "debt_adj"])
def test_text_price_reported_not_crashing(typ):
    rows = [_row("bob"), _row("bob" if typ == "buy" else "", payer="bob",
                              to="alice", price="abc", typ=typ)]
    result, _, missing = _process(rows)
    assert result == {"bob": {"alice": 30.0}}   # first row unaffected
    assert missing == {3: ["price 'abc' is not a number"]}


def test_numeric_text_price_accepted():
    result, _, _ = _process([_row("bob", price=" 30 ")])
    assert result == {"bob": {"alice": 30.0}}


def test_pay_missing_to_reported():
    _, _, missing = _process([_row("bob"), _row(payer="bob", to="", price=5,
                                                typ="pay")])
    assert missing == {3: ["missing to"]}


def test_pay_to_new_person_is_a_known_user():
    # Add user + drag + 还钱 in the UI writes a pay row to a name that
    # appears nowhere else in the sheet
    result, _, missing = _process([_row("bob"),
                                   _row(payer="bob", to="dave", price=5,
                                        typ="pay")])
    assert missing == {}
    assert result["dave"] == {"bob": 5.0}


def test_debt_trans_with_share_in_who_reported():
    rows = [_row("bob,carol"),
            _row("carol(1)", payer="bob", to="alice", price=2,
                 typ="debt_trans")]
    _, _, missing = _process(rows)
    assert "single name" in missing[3][0]


def test_type_is_case_insensitive_and_unknown_type_reported():
    result, _, missing = _process([_row("bob", typ="Buy "),
                                   _row("bob", typ="refund")])
    assert result == {"bob": {"alice": 30.0}}
    assert missing == {3: ["unknown type 'refund'"]}


def test_bad_date_counted_but_flagged():
    result, user_stat, missing = _process([_row("bob", date="2025/04/01")])
    assert result == {"bob": {"alice": 30.0}}
    assert "date not recognised" in missing[2][0]
