"""
Unit, Edge-Case, and Ground-Truth Accuracy Tests for Task 3 Association Rule Miner (`tests/test_miner.py`).
"""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

from backend.config import BASE_DIR, DATA_DIR, OUTPUT_DIR
from backend.miner import (
    generate_association_rules,
    load_transactions,
    mine,
    mine_frequent_itemsets,
    verify_against_answer_key,
    write_mining_outputs,
)


def test_empty_transactions_edge_case():
    freq, cands, freq_by_k = mine_frequent_itemsets([], min_count=1)
    assert freq == {}
    assert cands == {}
    assert freq_by_k == {}

    freq2, rules2, tel2 = mine([], min_support=0.5, min_confidence=0.6, return_telemetry=True)
    assert freq2 == {}
    assert rules2 == []
    assert tel2["n_transactions"] == 0
    assert tel2["n_frequent"] == 0
    assert tel2["n_rules"] == 0


def test_duplicate_items_in_single_transaction_deduplicated():
    # Each transaction is defined as a mathematical set of item IDs
    raw_lines = [
        "10 10 20 20 30",
        "10 20 30",
        "10 20",
        "10 30",
    ]
    tx = load_transactions(raw_lines)
    assert tx[0] == [10, 20, 30]
    freq, rules, tel = mine(tx, min_support=0.5, min_confidence=0.75, return_telemetry=True)
    assert freq[(10,)] == 4
    assert freq[(10, 20)] == 3
    assert freq[(10, 30)] == 3
    assert freq[(10, 20, 30)] == 2
    # Rule (20,) -> (10,) has confidence 3/3 = 1.0
    rule_map = {(A, C): (cnt, conf) for A, C, cnt, conf in rules}
    assert ((20,), (10,)) in rule_map
    assert rule_map[((20,), (10,))][0] == 3
    assert abs(rule_map[((20,), (10,))][1] - 1.0) < 1e-9


def test_single_item_baskets_produce_no_rules():
    tx = [[1], [2], [1], [3], [1]]
    freq, rules, tel = mine(tx, min_support=0.4, min_confidence=0.5, return_telemetry=True)
    assert freq == {(1,): 3}
    assert rules == []
    assert tel["frequent_by_size"] == {1: 1}


def test_high_support_threshold_returns_empty():
    tx = [[1, 2], [2, 3], [3, 4], [4, 5]]
    freq, rules = mine(tx, min_support=0.9, min_confidence=0.6)
    assert freq == {}
    assert rules == []


def test_exact_confidence_boundary_0_6():
    # 5 transactions with item 1; 3 of them also have item 2 -> confidence(1 -> 2) = 3/5 = 0.600000
    tx = [
        [1, 2],
        [1, 2],
        [1, 2],
        [1, 3],
        [1, 4],
    ]
    freq, rules = mine(tx, min_support=0.4, min_confidence=0.6)
    assert (1, 2) in freq and freq[(1, 2)] == 3
    rule_pairs = {(A, C): conf for A, C, _, conf in rules}
    assert ((1,), (2,)) in rule_pairs
    assert abs(rule_pairs[((1,), (2,))] - 0.6) < 1e-9


def test_invalid_parameters_raise_value_error():
    with pytest.raises(ValueError):
        mine([[1, 2]], min_support=0.0, min_confidence=0.6)
    with pytest.raises(ValueError):
        mine([[1, 2]], min_support=1.2, min_confidence=0.6)
    with pytest.raises(ValueError):
        mine([[1, 2]], min_support=0.5, min_confidence=0.0)
    with pytest.raises(ValueError):
        mine([[1, 2]], min_support=0.5, min_confidence=1.5)


def test_missing_file_raises_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_transactions("non_existent_transactions_file_xyz.txt")


def test_csv_output_formatting(tmp_path: Path):
    tx = [[1, 2, 3], [1, 2, 3], [1, 2], [1, 3]]
    freq, rules = mine(tx, min_support=0.5, min_confidence=0.6, output_dir=tmp_path, prefix="test_")
    fi_file = tmp_path / "test_frequent_itemsets.csv"
    ar_file = tmp_path / "test_rules.csv"
    assert fi_file.is_file()
    assert ar_file.is_file()

    with fi_file.open("r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == len(freq)
    assert set(rows[0].keys()) == {"itemset", "count"}

    with ar_file.open("r", encoding="utf-8") as f:
        r_rows = list(csv.DictReader(f))
    assert len(r_rows) == len(rules)
    assert set(r_rows[0].keys()) == {"antecedent", "consequent", "count", "confidence"}
    # Confidence must be formatted with 6 decimal places
    for r in r_rows:
        assert len(r["confidence"].split(".")[1]) == 6


def test_dev_dataset_exact_agreement_with_answer_key():
    dev_freq, dev_rules, dev_tel = mine(
        DATA_DIR / "dev_transactions.txt",
        min_support=0.003,
        min_confidence=0.6,
        return_telemetry=True,
    )
    assert dev_tel["n_transactions"] == 50000
    assert dev_tel["min_count"] == 150
    assert dev_tel["n_frequent"] == 12141
    assert dev_tel["n_rules"] == 125999

    ver = verify_against_answer_key(
        dev_freq,
        dev_rules,
        DATA_DIR / "dev_frequent_itemsets.csv",
        DATA_DIR / "dev_rules.csv",
    )
    assert ver["exact_match"] is True
    assert ver["itemsets"]["missing_count"] == 0
    assert ver["itemsets"]["extra_count"] == 0
    assert ver["itemsets"]["wrong_count_entries"] == 0
    assert ver["rules"]["missing_count"] == 0
    assert ver["rules"]["extra_count"] == 0
    assert ver["rules"]["wrong_entries"] == 0


def test_full_dataset_deliverables_exist_and_match_ground_truth():
    fi_out = OUTPUT_DIR / "frequent_itemsets.csv"
    ar_out = OUTPUT_DIR / "rules.csv"
    assert fi_out.is_file()
    assert ar_out.is_file()
    assert (BASE_DIR / "frequent_itemsets.csv").is_file()
    assert (BASE_DIR / "rules.csv").is_file()

    # Verify line counts (header + 11,733 itemsets; header + 110,402 rules)
    with fi_out.open("r", encoding="utf-8") as f:
        fi_lines = sum(1 for _ in f)
    with ar_out.open("r", encoding="utf-8") as f:
        ar_lines = sum(1 for _ in f)

    assert fi_lines == 11733 + 1
    assert ar_lines == 110402 + 1

