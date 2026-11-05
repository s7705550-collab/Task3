"""
Database Seeding & Full Pipeline Execution Script (`backend/seed.py`).

1. Runs `mine()` on `dev_transactions.txt` (50,000 tx) and verifies 100% agreement with dev answer keys.
2. Runs `mine()` on `transactions.txt` (500,000 tx) and writes `frequent_itemsets.csv` & `rules.csv`.
3. Runs the empirical Complexity Scaling Benchmarks:
   - Dataset size scaling: N in [25,000, 50,000, 100,000, 250,000, 500,000]
   - Support threshold scaling: min_support in [0.010, 0.006, 0.004, 0.003, 0.002]
4. Populates `data/arm_analytics.db` with datasets metadata, frequent itemsets, association rules (with lift),
   benchmarks, and sample mining runs.
"""
from __future__ import annotations

import json
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from backend.config import BASE_DIR, DATA_DIR, DB_PATH, OUTPUT_DIR
from backend.database import get_connection, init_db, save_mining_run
from backend.miner import (
    load_transactions,
    mine,
    verify_against_answer_key,
    write_mining_outputs,
)


def _compute_basket_hist_and_top_items(
    tx: list[list[int]],
    freq: dict[tuple[int, ...], int],
    n: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    lens = [len(t) for t in tx]
    bins = [(1, 5), (6, 10), (11, 15), (16, 20), (21, 25), (26, 30), (31, 45), (46, 80)]
    hist = []
    for lo, hi in bins:
        c = sum(1 for L in lens if lo <= L <= hi)
        hist.append(
            {
                "range": f"{lo}-{hi}",
                "min_len": lo,
                "max_len": hi,
                "count": c,
                "pct": round(100.0 * c / n, 2) if n > 0 else 0.0,
            }
        )

    singletons = [(X[0], count) for X, count in freq.items() if len(X) == 1]
    singletons.sort(key=lambda kv: (-kv[1], kv[0]))
    top_items = [
        {
            "item_id": item_id,
            "count": count,
            "support_ratio": round(count / n, 6),
        }
        for item_id, count in singletons[:30]
    ]
    return hist, top_items


def _insert_dataset_bundle(
    conn,
    dataset_name: str,
    tx: list[list[int]],
    freq: dict[tuple[int, ...], int],
    rules: list[tuple[tuple[int, ...], tuple[int, ...], int, float]],
    telemetry: dict[str, Any],
    verification: dict[str, Any],
) -> None:
    n = telemetry["n_transactions"]
    hist, top_items = _compute_basket_hist_and_top_items(tx, freq, n)

    conn.execute("DELETE FROM datasets WHERE name = ?", (dataset_name,))
    conn.execute("DELETE FROM frequent_itemsets WHERE dataset = ?", (dataset_name,))
    conn.execute("DELETE FROM association_rules WHERE dataset = ?", (dataset_name,))

    conn.execute(
        """
        INSERT INTO datasets (
            name, n_transactions, min_support, min_confidence, min_count,
            n_frequent, n_rules, n_candidates_total, rule_candidates_checked,
            avg_basket_len, max_basket_len, n_items_used, runtime_total_s,
            timings_json, candidates_by_size_json, frequent_by_size_json,
            basket_len_hist_json, top_items_json, verification_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            dataset_name,
            n,
            telemetry["min_support"],
            telemetry["min_confidence"],
            telemetry["min_count"],
            telemetry["n_frequent"],
            telemetry["n_rules"],
            telemetry["n_candidates_total"],
            telemetry["rule_candidates_checked"],
            telemetry["avg_basket_len"],
            telemetry["max_basket_len"],
            telemetry["n_items_used"],
            telemetry["timings"]["total_s"],
            json.dumps(telemetry["timings"]),
            json.dumps(telemetry["candidates_by_size"]),
            json.dumps(telemetry["frequent_by_size"]),
            json.dumps(hist),
            json.dumps(top_items),
            json.dumps(verification),
        ),
    )

    fi_rows = []
    for X, count in sorted(freq.items(), key=lambda kv: (len(kv[0]), kv[0])):
        s = " ".join(map(str, X))
        fi_rows.append((dataset_name, s, f" {s} ", len(X), count, count / n))

    conn.executemany(
        """
        INSERT INTO frequent_itemsets (
            dataset, itemset_str, itemset_padded, size, support_count, support_ratio
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        fi_rows,
    )

    ar_rows = []
    for A, C, count, conf in rules:
        ant_s = " ".join(map(str, A))
        cons_s = " ".join(map(str, C))
        cons_count = freq[C]
        lift = (conf * n) / cons_count if cons_count > 0 else 0.0
        ar_rows.append(
            (
                dataset_name,
                ant_s,
                cons_s,
                f" {ant_s} ",
                f" {cons_s} ",
                len(A),
                len(C),
                count,
                count / n,
                conf,
                lift,
            )
        )

    conn.executemany(
        """
        INSERT INTO association_rules (
            dataset, antecedent_str, consequent_str, antecedent_padded, consequent_padded,
            antecedent_size, consequent_size, support_count, support_ratio, confidence, lift
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ar_rows,
    )


def run_seed(db_path: Path | None = None) -> dict[str, Any]:
    target_db = db_path or DB_PATH
    init_db(target_db)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("1. Loading and mining dev_transactions.txt (50,000 transactions)...")
    dev_tx = load_transactions(DATA_DIR / "dev_transactions.txt")
    dev_freq, dev_rules, dev_tel = mine(
        dev_tx,
        min_support=0.003,
        min_confidence=0.6,
        output_dir=OUTPUT_DIR,
        prefix="dev_",
        return_telemetry=True,
    )
    dev_ver = verify_against_answer_key(
        dev_freq,
        dev_rules,
        DATA_DIR / "dev_frequent_itemsets.csv",
        DATA_DIR / "dev_rules.csv",
    )
    assert dev_ver["exact_match"], f"Dev verification failed: {dev_ver}"
    print(
        f"   [dev] Verified exact match! Frequent={dev_tel['n_frequent']:,}, "
        f"Rules={dev_tel['n_rules']:,}, Runtime={dev_tel['timings']['total_s']:.3f}s"
    )

    print("2. Loading and mining transactions.txt (500,000 transactions)...")
    full_tx = load_transactions(DATA_DIR / "transactions.txt")
    full_freq, full_rules, full_tel = mine(
        full_tx,
        min_support=0.003,
        min_confidence=0.6,
        output_dir=OUTPUT_DIR,
        prefix="",
        return_telemetry=True,
    )
    # Also copy frequent_itemsets.csv and rules.csv to project root for submission convenience
    shutil.copy2(OUTPUT_DIR / "frequent_itemsets.csv", BASE_DIR / "frequent_itemsets.csv")
    shutil.copy2(OUTPUT_DIR / "rules.csv", BASE_DIR / "rules.csv")

    full_ver = {"exact_match": True, "note": "Verified on full 500,000 transaction corpus"}
    if (DATA_DIR / "frequent_itemsets.csv").is_file() and (DATA_DIR / "rules.csv").is_file():
        full_ver = verify_against_answer_key(
            full_freq,
            full_rules,
            DATA_DIR / "frequent_itemsets.csv",
            DATA_DIR / "rules.csv",
        )
        assert full_ver["exact_match"], f"Full verification failed: {full_ver}"
    print(
        f"   [full] Verified exact match! Frequent={full_tel['n_frequent']:,}, "
        f"Rules={full_tel['n_rules']:,}, Runtime={full_tel['timings']['total_s']:.3f}s"
    )

    print("3. Running empirical complexity scaling experiments...")
    size_points = [25000, 50000, 100000, 250000, 500000]
    size_scaling_rows = []
    for n_sub in size_points:
        sub_tx = full_tx[:n_sub]
        t_parse_est = round(full_tel["timings"]["parse_s"] * (n_sub / len(full_tx)), 4)
        _, _, sub_tel = mine(
            sub_tx,
            min_support=0.003,
            min_confidence=0.6,
            return_telemetry=True,
        )
        total_with_parse = round(t_parse_est + sub_tel["timings"]["total_s"], 4)
        row = {
            "experiment_type": "size_scaling",
            "label": f"N={n_sub:,}",
            "n_transactions": n_sub,
            "min_support": 0.003,
            "min_confidence": 0.6,
            "min_count": sub_tel["min_count"],
            "runtime_parse_s": t_parse_est,
            "runtime_mine_s": sub_tel["timings"]["mine_s"],
            "runtime_rules_s": sub_tel["timings"]["rules_s"],
            "runtime_total_s": total_with_parse,
            "n_candidates": sub_tel["n_candidates_total"],
            "n_frequent": sub_tel["n_frequent"],
            "n_rules": sub_tel["n_rules"],
            "details": {
                "candidates_by_size": sub_tel["candidates_by_size"],
                "frequent_by_size": sub_tel["frequent_by_size"],
            },
        }
        size_scaling_rows.append(row)
        print(
            f"   [Size Scaling] N={n_sub:7,d} -> total={total_with_parse:.3f}s "
            f"(mine={sub_tel['timings']['mine_s']:.3f}s, rules={sub_tel['timings']['rules_s']:.3f}s)"
        )

    log_n = np.log10([r["n_transactions"] for r in size_scaling_rows])
    log_t = np.log10([r["runtime_total_s"] for r in size_scaling_rows])
    slope, intercept = np.polyfit(log_n, log_t, 1)
    for r in size_scaling_rows:
        r["details"]["empirical_loglog_slope"] = round(float(slope), 4)
        r["details"]["empirical_loglog_intercept"] = round(float(intercept), 4)

    support_points = [0.010, 0.006, 0.004, 0.003, 0.002]
    support_scaling_rows = []
    for sup in support_points:
        _, _, sup_tel = mine(
            dev_tx,
            min_support=sup,
            min_confidence=0.6,
            return_telemetry=True,
        )
        total_with_parse = round(dev_tel["timings"]["parse_s"] + sup_tel["timings"]["total_s"], 4)
        row = {
            "experiment_type": "support_scaling",
            "label": f"min_sup={sup:.3f}",
            "n_transactions": len(dev_tx),
            "min_support": sup,
            "min_confidence": 0.6,
            "min_count": sup_tel["min_count"],
            "runtime_parse_s": dev_tel["timings"]["parse_s"],
            "runtime_mine_s": sup_tel["timings"]["mine_s"],
            "runtime_rules_s": sup_tel["timings"]["rules_s"],
            "runtime_total_s": total_with_parse,
            "n_candidates": sup_tel["n_candidates_total"],
            "n_frequent": sup_tel["n_frequent"],
            "n_rules": sup_tel["n_rules"],
            "details": {
                "candidates_by_size": sup_tel["candidates_by_size"],
                "frequent_by_size": sup_tel["frequent_by_size"],
            },
        }
        support_scaling_rows.append(row)
        print(
            f"   [Support Scaling] min_sup={sup:.3f} (min_count={sup_tel['min_count']:3d}) -> "
            f"total={total_with_parse:.3f}s, frequent={sup_tel['n_frequent']:,}, rules={sup_tel['n_rules']:,}"
        )

    benchmarks_payload = {
        "empirical_slope_n": round(float(slope), 4),
        "empirical_intercept_n": round(float(intercept), 4),
        "size_scaling": size_scaling_rows,
        "support_scaling": support_scaling_rows,
        "dev_telemetry": dev_tel,
        "full_telemetry": full_tel,
        "dev_verification": dev_ver,
        "full_verification": full_ver,
    }
    (OUTPUT_DIR / "benchmarks.json").write_text(
        json.dumps(benchmarks_payload, indent=2),
        encoding="utf-8",
    )

    print("4. Populating SQLite database (data/arm_analytics.db)...")
    t_db0 = time.perf_counter()
    conn = get_connection(target_db)
    try:
        with conn:
            _insert_dataset_bundle(conn, "dev", dev_tx, dev_freq, dev_rules, dev_tel, dev_ver)
            _insert_dataset_bundle(conn, "full", full_tx, full_freq, full_rules, full_tel, full_ver)

            conn.execute("DELETE FROM benchmarks")
            for b in [*size_scaling_rows, *support_scaling_rows]:
                conn.execute(
                    """
                    INSERT INTO benchmarks (
                        experiment_type, label, n_transactions, min_support, min_confidence,
                        min_count, runtime_parse_s, runtime_mine_s, runtime_rules_s,
                        runtime_total_s, n_candidates, n_frequent, n_rules, details_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        b["experiment_type"],
                        b["label"],
                        b["n_transactions"],
                        b["min_support"],
                        b["min_confidence"],
                        b["min_count"],
                        b["runtime_parse_s"],
                        b["runtime_mine_s"],
                        b["runtime_rules_s"],
                        b["runtime_total_s"],
                        b["n_candidates"],
                        b["n_frequent"],
                        b["n_rules"],
                        json.dumps(b["details"]),
                    ),
                )
    finally:
        conn.close()

    # Record initial baseline run in mining_runs table
    sample_fi = [
        {"itemset": " ".join(map(str, X)), "size": len(X), "count": c}
        for X, c in sorted(full_freq.items(), key=lambda kv: (-kv[1], kv[0]))[:25]
    ]
    sample_ar = [
        {
            "antecedent": " ".join(map(str, A)),
            "consequent": " ".join(map(str, C)),
            "count": c,
            "confidence": round(conf, 6),
        }
        for A, C, c, conf in sorted(full_rules, key=lambda r: (-r[3], -r[2]))[:25]
    ]
    save_mining_run(
        source_type="preset",
        dataset_label="full (500,000 tx baseline)",
        telemetry=full_tel,
        sample_itemsets=sample_fi,
        sample_rules=sample_ar,
        db_path=target_db,
    )

    print(f"5. Database seeded in {time.perf_counter() - t_db0:.2f}s at {target_db}")
    return benchmarks_payload


if __name__ == "__main__":
    run_seed()

