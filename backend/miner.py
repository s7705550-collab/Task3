"""
Core Association Rule Mining Engine (Vertical-Bitset Eclat + Confidence-Pruned Rules).

Complies strictly with Task 3 rules in RC3_AI_Hackathon.docx:
- Uses only Python standard library + NumPy.
- Never reads or loads any answer key during mining.
- Computes exact frequent itemsets: count(X) >= ceil(min_support * n), |X| >= 1.
- Computes exact association rules A -> C: A, C non-empty, disjoint, A u C frequent,
  count(A u C) / count(A) >= min_confidence.
- Tracks exact candidate counts examined and frequent itemsets found at each size k.
"""
from __future__ import annotations

import csv
import math
import os
import time
from pathlib import Path
from typing import Iterable

import numpy as np

# Fallback lookup table for 8-bit popcount if np.bitwise_count is unavailable
_POPCOUNT_TBL = np.array([bin(i).count("1") for i in range(256)], dtype=np.uint8)


def popcount_uint64(a64: np.ndarray) -> int:
    """Fast hardware-accelerated population count over a uint64 bitset array."""
    if hasattr(np, "bitwise_count"):
        return int(np.bitwise_count(a64).sum())
    return int(_POPCOUNT_TBL[a64.view(np.uint8)].sum())


def load_transactions(source: str | Path | Iterable[str | Iterable[int]]) -> list[list[int]]:
    """
    Parse transactions from a file path or iterable of lines/item collections.
    Each transaction is returned as a sorted list of unique non-negative integer item IDs.
    """
    transactions: list[list[int]] = []
    if isinstance(source, (str, Path)):
        path = Path(source)
        if not path.is_file():
            raise FileNotFoundError(f"Transaction file not found: {path}")
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if not s:
                    continue
                items = sorted({int(tok) for tok in s.split()})
                if items:
                    transactions.append(items)
    else:
        for entry in source:
            if isinstance(entry, str):
                s = entry.strip()
                if not s:
                    continue
                items = sorted({int(tok) for tok in s.split()})
            else:
                items = sorted({int(x) for x in entry})
            if items:
                transactions.append(items)
    return transactions


def mine_frequent_itemsets(
    transactions: list[list[int]],
    min_count: int,
) -> tuple[dict[tuple[int, ...], int], dict[int, int], dict[int, int]]:
    """
    Exact Vertical-Bitset Eclat Frequent Itemset Miner with Candidate Telemetry.

    Parameters
    ----------
    transactions : list[list[int]]
        List of transactions, each a sorted list of unique integer item IDs.
    min_count : int
        Minimum support count threshold: ceil(min_support * n_transactions).

    Returns
    -------
    freq : dict[tuple[int, ...], int]
        Mapping from sorted itemset tuple X to exact support count(X).
    candidates_by_size : dict[int, int]
        Number of candidate itemsets examined at each itemset size k.
    frequent_by_size : dict[int, int]
        Number of frequent itemsets found at each itemset size k.
    """
    n = len(transactions)
    if n == 0 or min_count <= 0:
        return {}, {}, {}

    lens = np.fromiter(map(len, transactions), dtype=np.int64, count=n)
    total_tokens = int(lens.sum())
    if total_tokens == 0:
        return {}, {}, {}

    flat = np.fromiter(
        (item for tx in transactions for item in tx),
        dtype=np.int32,
        count=total_tokens,
    )
    tid = np.repeat(np.arange(n, dtype=np.int32), lens)
    cnt = np.bincount(flat)

    distinct_items = int(np.count_nonzero(cnt))
    freq_items = np.where(cnt >= min_count)[0]

    candidates_by_size: dict[int, int] = {1: distinct_items}
    frequent_by_size: dict[int, int] = {}
    if len(freq_items) == 0:
        return {}, candidates_by_size, frequent_by_size

    frequent_by_size[1] = int(len(freq_items))

    # Group transaction IDs per item via stable argsort
    order = np.argsort(flat, kind="stable")
    flat_s = flat[order]
    tid_s = tid[order]
    bounds = np.searchsorted(flat_s, np.arange(len(cnt) + 1))

    # Pack each frequent item's transaction ID list into a 64-bit aligned bitset
    nbytes = ((n + 7) // 8 + 7) // 8 * 8
    cands: list[tuple[int, np.ndarray, int]] = []
    for it in freq_items:
        arr = np.zeros(nbytes * 8, dtype=bool)
        arr[tid_s[bounds[it] : bounds[it + 1]]] = True
        bits = np.packbits(arr).view(np.uint64)
        cands.append((int(it), bits, int(cnt[it])))

    # Ascending support order shrinks equivalence classes fastest during DFS
    cands.sort(key=lambda x: (x[2], x[0]))
    result: dict[tuple[int, ...], int] = {}

    def eclat_dfs(prefix: list[int], eq_class: list[tuple[int, np.ndarray, int]]) -> None:
        next_size = len(prefix) + 2
        for k_idx, (it, b, c) in enumerate(eq_class):
            p = prefix + [it]
            key = tuple(sorted(p))
            result[key] = c

            rem = len(eq_class) - (k_idx + 1)
            if rem > 0:
                candidates_by_size[next_size] = candidates_by_size.get(next_size, 0) + rem

            nxt: list[tuple[int, np.ndarray, int]] = []
            for jt, bj, _ in eq_class[k_idx + 1 :]:
                inter = b & bj
                cc = popcount_uint64(inter)
                if cc >= min_count:
                    nxt.append((jt, inter, cc))
            if nxt:
                frequent_by_size[next_size] = frequent_by_size.get(next_size, 0) + len(nxt)
                eclat_dfs(p, nxt)

    eclat_dfs([], cands)
    return result, candidates_by_size, frequent_by_size


def generate_association_rules(
    freq: dict[tuple[int, ...], int],
    min_confidence: float,
) -> tuple[list[tuple[tuple[int, ...], tuple[int, ...], int, float]], int]:
    """
    Generate all valid association rules A -> C from frequent itemsets.

    Rule definition:
      - A, C non-empty, disjoint, A u C = X in freq
      - confidence = count(X) / count(A) >= min_confidence
      - sorted ascending by (A, C)

    Returns
    -------
    rules : list of (antecedent_tuple, consequent_tuple, support_count, confidence)
    rule_candidates_checked : int
        Total number of (A, X \\ A) partitions evaluated.
    """
    rules: list[tuple[tuple[int, ...], tuple[int, ...], int, float]] = []
    rule_candidates_checked = 0

    for X, c in freq.items():
        k = len(X)
        if k < 2:
            continue
        # Maximum antecedent count that can still satisfy c / count(A) >= min_confidence
        max_ca = c / min_confidence + 1e-12
        n_masks = (1 << k) - 1
        rule_candidates_checked += n_masks - 1
        for mask in range(1, n_masks):
            A = tuple(X[i] for i in range(k) if (mask >> i) & 1)
            ca = freq[A]
            if ca <= max_ca and c >= min_confidence * ca - 1e-12:
                C = tuple(X[i] for i in range(k) if not ((mask >> i) & 1))
                rules.append((A, C, c, c / ca))

    rules.sort()
    return rules, rule_candidates_checked


def write_mining_outputs(
    output_dir: str | Path,
    freq: dict[tuple[int, ...], int],
    rules: list[tuple[tuple[int, ...], tuple[int, ...], int, float]],
    prefix: str = "",
) -> tuple[Path, Path]:
    """
    Write frequent_itemsets.csv and rules.csv in the exact format required by Task 3:
    - frequent_itemsets.csv: columns itemset,count; sorted by (len(X), X)
    - rules.csv: columns antecedent,consequent,count,confidence (6 decimals); sorted by (A, C)
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    itemsets_file = out_path / f"{prefix}frequent_itemsets.csv"
    rules_file = out_path / f"{prefix}rules.csv"

    with itemsets_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["itemset", "count"])
        for X, count in sorted(freq.items(), key=lambda kv: (len(kv[0]), kv[0])):
            writer.writerow([" ".join(map(str, X)), count])

    with rules_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["antecedent", "consequent", "count", "confidence"])
        for A, C, count, conf in rules:
            writer.writerow([" ".join(map(str, A)), " ".join(map(str, C)), count, f"{conf:.6f}"])

    return itemsets_file, rules_file


def mine(
    transactions_input: str | Path | list[list[int]] | Iterable[str],
    min_support: float = 0.003,
    min_confidence: float = 0.6,
    output_dir: str | Path | None = None,
    prefix: str = "",
    return_telemetry: bool = False,
):
    """
    Complete end-to-end Association Rule Mining pipeline for Task 3.

    Parameters
    ----------
    transactions_input : path to transactions file or in-memory transaction list
    min_support : float in (0, 1] (default 0.003)
    min_confidence : float in (0, 1] (default 0.6)
    output_dir : optional directory to write frequent_itemsets.csv and rules.csv
    prefix : optional filename prefix (e.g. '' or 'dev_')
    return_telemetry : if True, returns (freq, rules, telemetry_dict)

    Returns
    -------
    (freq, rules) or (freq, rules, telemetry)
    """
    if not (0.0 < min_support <= 1.0):
        raise ValueError(f"min_support must be in (0, 1], got {min_support}")
    if not (0.0 < min_confidence <= 1.0):
        raise ValueError(f"min_confidence must be in (0, 1], got {min_confidence}")

    t0 = time.perf_counter()
    if isinstance(transactions_input, list) and (
        len(transactions_input) == 0 or isinstance(transactions_input[0], list)
    ):
        tx = transactions_input
    else:
        tx = load_transactions(transactions_input)
    t_parse = time.perf_counter()

    n = len(tx)
    min_count = math.ceil(min_support * n) if n > 0 else 0

    freq, candidates_by_size, frequent_by_size = mine_frequent_itemsets(tx, min_count)
    t_mine = time.perf_counter()

    rules, rule_candidates_checked = generate_association_rules(freq, min_confidence)
    t_rules = time.perf_counter()

    if output_dir is not None:
        write_mining_outputs(output_dir, freq, rules, prefix=prefix)
    t_end = time.perf_counter()

    lens = [len(t) for t in tx] if n > 0 else [0]
    telemetry = {
        "n_transactions": n,
        "min_support": min_support,
        "min_confidence": min_confidence,
        "min_count": min_count,
        "n_frequent": len(freq),
        "n_rules": len(rules),
        "n_candidates_total": int(sum(candidates_by_size.values())),
        "rule_candidates_checked": rule_candidates_checked,
        "candidates_by_size": {int(k): int(v) for k, v in sorted(candidates_by_size.items())},
        "frequent_by_size": {int(k): int(v) for k, v in sorted(frequent_by_size.items())},
        "avg_basket_len": round(sum(lens) / n, 2) if n > 0 else 0.0,
        "max_basket_len": int(max(lens)) if n > 0 else 0,
        "n_items_used": int(candidates_by_size.get(1, 0)),
        "timings": {
            "parse_s": round(t_parse - t0, 4),
            "mine_s": round(t_mine - t_parse, 4),
            "rules_s": round(t_rules - t_mine, 4),
            "write_s": round(t_end - t_rules, 4),
            "total_s": round(t_end - t0, 4),
        },
    }

    if return_telemetry:
        return freq, rules, telemetry
    return freq, rules


def verify_against_answer_key(
    freq: dict[tuple[int, ...], int],
    rules: list[tuple[tuple[int, ...], tuple[int, ...], int, float]],
    expected_itemsets_csv: str | Path,
    expected_rules_csv: str | Path,
) -> dict:
    """
    Compare mined frequent itemsets and association rules against a ground-truth answer key.
    Used ONLY for dev-set correctness reporting and automated testing.
    """
    exp_freq: dict[tuple[int, ...], int] = {}
    with Path(expected_itemsets_csv).open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            itemset = tuple(map(int, row["itemset"].split()))
            exp_freq[itemset] = int(row["count"])

    missing_itemsets = set(exp_freq.keys()) - set(freq.keys())
    extra_itemsets = set(freq.keys()) - set(exp_freq.keys())
    wrong_counts = {
        k: (freq[k], exp_freq[k])
        for k in (set(freq.keys()) & set(exp_freq.keys()))
        if freq[k] != exp_freq[k]
    }

    exp_rules: dict[tuple[tuple[int, ...], tuple[int, ...]], tuple[int, str]] = {}
    with Path(expected_rules_csv).open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            A = tuple(map(int, row["antecedent"].split()))
            C = tuple(map(int, row["consequent"].split()))
            exp_rules[(A, C)] = (int(row["count"]), row["confidence"])

    pred_rules: dict[tuple[tuple[int, ...], tuple[int, ...]], tuple[int, str]] = {
        (A, C): (c, f"{conf:.6f}") for A, C, c, conf in rules
    }

    missing_rules = set(exp_rules.keys()) - set(pred_rules.keys())
    extra_rules = set(pred_rules.keys()) - set(exp_rules.keys())
    wrong_rules = {
        k: (pred_rules[k], exp_rules[k])
        for k in (set(pred_rules.keys()) & set(exp_rules.keys()))
        if pred_rules[k] != exp_rules[k]
    }

    exact_match = (
        len(missing_itemsets) == 0
        and len(extra_itemsets) == 0
        and len(wrong_counts) == 0
        and len(missing_rules) == 0
        and len(extra_rules) == 0
        and len(wrong_rules) == 0
    )

    return {
        "exact_match": exact_match,
        "itemsets": {
            "expected": len(exp_freq),
            "predicted": len(freq),
            "missing_count": len(missing_itemsets),
            "extra_count": len(extra_itemsets),
            "wrong_count_entries": len(wrong_counts),
            "examples_missing": [list(x) for x in sorted(missing_itemsets)[:5]],
            "examples_extra": [list(x) for x in sorted(extra_itemsets)[:5]],
            "examples_wrong": [
                {"itemset": list(k), "pred": v[0], "exp": v[1]}
                for k, v in list(wrong_counts.items())[:5]
            ],
        },
        "rules": {
            "expected": len(exp_rules),
            "predicted": len(pred_rules),
            "missing_count": len(missing_rules),
            "extra_count": len(extra_rules),
            "wrong_entries": len(wrong_rules),
            "examples_missing": [
                {"antecedent": list(a), "consequent": list(c)}
                for a, c in sorted(missing_rules)[:5]
            ],
            "examples_extra": [
                {"antecedent": list(a), "consequent": list(c)}
                for a, c in sorted(extra_rules)[:5]
            ],
            "examples_wrong": [
                {
                    "antecedent": list(k[0]),
                    "consequent": list(k[1]),
                    "pred": v[0],
                    "exp": v[1],
                }
                for k, v in list(wrong_rules.items())[:5]
            ],
        },
    }

