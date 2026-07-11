import random

import pytest

import Processor
from Content import Content
from Processor import settle

TAX_RATE = 0.15


def _balances_from_matrix(result, users):
    """Net balance per user. Negative = owes money overall."""
    balances = {u: 0.0 for u in users}
    for debtor in result:
        for creditor, amount in result[debtor].items():
            balances[debtor] -= amount
            balances[creditor] += amount
    return balances


def _apply_transfers(balances, transfers):
    for debtor in transfers:
        for creditor, amount in transfers[debtor].items():
            balances[debtor] += amount
            balances[creditor] -= amount


def assert_settlement_properties(result, transfers, users):
    balances = _balances_from_matrix(result, users)
    n_nonzero = sum(1 for v in balances.values() if abs(v) >= 0.01)
    _apply_transfers(balances, transfers)
    # P1: everything settles
    for user, residual in balances.items():
        assert abs(residual) < 0.01, f"{user} residual {residual}"
    # P2: no zero/negative transfers
    count = 0
    for debtor in transfers:
        for creditor, amount in transfers[debtor].items():
            assert amount > 0
            count += 1
    # P3: bounded transfer count
    assert count <= max(n_nonzero - 1, 0)


def _readme_records():
    # README example: A paid 10 split A,B,C; B paid 5 for A;
    # C paid 6 split A,B.
    base = {"category": "x", "product": "p", "tax_flg": "",
            "tag": "", "price": 0}
    return [
        dict(base, date="2025-01-01", type="buy", price=10,
             **{"from": "A", "to": "m", "who": "A,B,C"}),
        dict(base, date="2025-01-02", type="buy", price=5,
             **{"from": "B", "to": "m", "who": "A"}),
        dict(base, date="2025-01-03", type="buy", price=6,
             **{"from": "C", "to": "m", "who": "A,B"}),
    ]


def test_readme_example_settles(sample_records):
    for records in (_readme_records(), sample_records):
        content = Content(records)
        proc = Processor.Processor()
        result, _, _ = proc.process(content, TAX_RATE)
        transfers = Processor.get_optimized(result, content)
        assert_settlement_properties(result, transfers,
                                     content.get_users())


def _apply_settle(balances, transfers):
    b = dict(balances)
    for debtor in transfers:
        for creditor, amount in transfers[debtor].items():
            b[debtor] += amount
            b[creditor] -= amount
    return b


def test_settle_float_noise():
    # 0.1 is inexact in binary; sums drift. Must settle to 0 cents.
    balances = {"a": -0.1, "b": -0.2, "c": 0.30000000000000004}
    transfers = settle(balances)
    residuals = _apply_settle(balances, transfers)
    assert all(abs(v) < 0.005 for v in residuals.values())


def test_exact_match_pairs_settle_directly():
    balances = {"a": -5.0, "b": 5.0, "c": -7.0, "d": 7.0}
    transfers = settle(balances)
    count = sum(len(v) for v in transfers.values())
    assert count == 2                     # naive greedy could do 3
    assert transfers["a"] == {"b": 5.0}
    assert transfers["c"] == {"d": 7.0}


def test_dp_beats_plain_greedy():
    # {-3,-2,+5} and {-4,+4}: optimal 3 transfers (2 + 1).
    # Largest-first greedy without grouping pairs -4 with +5 first
    # and needs 4.
    balances = {"a": -3.0, "b": -2.0, "c": 5.0,
                "d": -4.0, "e": 4.0}
    transfers = settle(balances)
    count = sum(len(v) for v in transfers.values())
    assert count == 3
    residuals = _apply_settle(balances, transfers)
    assert all(abs(v) < 0.01 for v in residuals.values())


def test_settle_large_random_terminates():
    rng = random.Random(42)
    balances = {f"u{i}": rng.randint(-500, 500) / 1.0
                for i in range(199)}
    balances["u199"] = -sum(balances.values())
    transfers = settle(balances)
    residuals = _apply_settle(balances, transfers)
    assert all(abs(v) < 0.01 for v in residuals.values())
    count = sum(len(v) for v in transfers.values())
    nonzero = sum(1 for v in balances.values() if abs(v) >= 0.01)
    assert count <= nonzero - 1
