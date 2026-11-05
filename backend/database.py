"""
SQLite Database Layer for Task 3 Association Rule Mining Web Application.

Manages schema creation, connection pooling, fast batch seeding, and analytical queries
for datasets, frequent itemsets, association rules, basket recommendations, benchmarks,
and custom mining runs.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.config import DB_PATH


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    target = Path(db_path) if db_path is not None else DB_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path | None = None) -> None:
    conn = get_connection(db_path)
    try:
        with conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS datasets (
                    name TEXT PRIMARY KEY,
                    n_transactions INTEGER NOT NULL,
                    min_support REAL NOT NULL,
                    min_confidence REAL NOT NULL,
                    min_count INTEGER NOT NULL,
                    n_frequent INTEGER NOT NULL,
                    n_rules INTEGER NOT NULL,
                    n_candidates_total INTEGER NOT NULL,
                    rule_candidates_checked INTEGER NOT NULL,
                    avg_basket_len REAL NOT NULL,
                    max_basket_len INTEGER NOT NULL,
                    n_items_used INTEGER NOT NULL,
                    runtime_total_s REAL NOT NULL,
                    timings_json TEXT NOT NULL,
                    candidates_by_size_json TEXT NOT NULL,
                    frequent_by_size_json TEXT NOT NULL,
                    basket_len_hist_json TEXT NOT NULL,
                    top_items_json TEXT NOT NULL,
                    verification_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS frequent_itemsets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dataset TEXT NOT NULL,
                    itemset_str TEXT NOT NULL,
                    itemset_padded TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    support_count INTEGER NOT NULL,
                    support_ratio REAL NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_fi_dataset_size_count
                    ON frequent_itemsets(dataset, size, support_count DESC);
                CREATE INDEX IF NOT EXISTS idx_fi_dataset_count
                    ON frequent_itemsets(dataset, support_count DESC);
                CREATE INDEX IF NOT EXISTS idx_fi_dataset_padded
                    ON frequent_itemsets(dataset, itemset_padded);

                CREATE TABLE IF NOT EXISTS association_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dataset TEXT NOT NULL,
                    antecedent_str TEXT NOT NULL,
                    consequent_str TEXT NOT NULL,
                    antecedent_padded TEXT NOT NULL,
                    consequent_padded TEXT NOT NULL,
                    antecedent_size INTEGER NOT NULL,
                    consequent_size INTEGER NOT NULL,
                    support_count INTEGER NOT NULL,
                    support_ratio REAL NOT NULL,
                    confidence REAL NOT NULL,
                    lift REAL NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_ar_dataset_conf
                    ON association_rules(dataset, confidence DESC, support_count DESC);
                CREATE INDEX IF NOT EXISTS idx_ar_dataset_lift
                    ON association_rules(dataset, lift DESC, confidence DESC);
                CREATE INDEX IF NOT EXISTS idx_ar_dataset_support
                    ON association_rules(dataset, support_count DESC, confidence DESC);
                CREATE INDEX IF NOT EXISTS idx_ar_dataset_sizes
                    ON association_rules(dataset, antecedent_size, consequent_size);

                CREATE TABLE IF NOT EXISTS benchmarks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    experiment_type TEXT NOT NULL,
                    label TEXT NOT NULL,
                    n_transactions INTEGER NOT NULL,
                    min_support REAL NOT NULL,
                    min_confidence REAL NOT NULL,
                    min_count INTEGER NOT NULL,
                    runtime_parse_s REAL NOT NULL,
                    runtime_mine_s REAL NOT NULL,
                    runtime_rules_s REAL NOT NULL,
                    runtime_total_s REAL NOT NULL,
                    n_candidates INTEGER NOT NULL,
                    n_frequent INTEGER NOT NULL,
                    n_rules INTEGER NOT NULL,
                    details_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS mining_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    dataset_label TEXT NOT NULL,
                    n_transactions INTEGER NOT NULL,
                    min_support REAL NOT NULL,
                    min_confidence REAL NOT NULL,
                    min_count INTEGER NOT NULL,
                    n_frequent INTEGER NOT NULL,
                    n_rules INTEGER NOT NULL,
                    n_candidates_total INTEGER NOT NULL,
                    runtime_total_s REAL NOT NULL,
                    telemetry_json TEXT NOT NULL,
                    sample_itemsets_json TEXT NOT NULL,
                    sample_rules_json TEXT NOT NULL
                );
                """
            )
    finally:
        conn.close()


def query_datasets_overview(db_path: Path | None = None) -> dict[str, Any]:
    conn = get_connection(db_path)
    try:
        rows = conn.execute("SELECT * FROM datasets ORDER BY name ASC").fetchall()
        result: dict[str, Any] = {}
        for r in rows:
            d = dict(r)
            for k in (
                "timings_json",
                "candidates_by_size_json",
                "frequent_by_size_json",
                "basket_len_hist_json",
                "top_items_json",
                "verification_json",
            ):
                clean_k = k.replace("_json", "")
                d[clean_k] = json.loads(d.pop(k))
            result[d["name"]] = d
        return result
    finally:
        conn.close()


def query_frequent_itemsets(
    dataset: str = "full",
    size: int | None = None,
    min_count: int | None = None,
    item_filter: str | None = None,
    sort_by: str = "support_desc",
    limit: int = 50,
    offset: int = 0,
    db_path: Path | None = None,
) -> dict[str, Any]:
    conn = get_connection(db_path)
    try:
        clauses = ["dataset = ?"]
        params: list[Any] = [dataset]

        if size is not None and size > 0:
            clauses.append("size = ?")
            params.append(int(size))

        if min_count is not None and min_count > 0:
            clauses.append("support_count >= ?")
            params.append(int(min_count))

        if item_filter:
            tokens = [t.strip() for t in item_filter.replace(",", " ").split() if t.strip()]
            for tok in tokens:
                if tok.isdigit():
                    clauses.append("itemset_padded LIKE ?")
                    params.append(f"% {int(tok)} %")

        where_sql = " AND ".join(clauses)
        order_map = {
            "support_desc": "support_count DESC, size ASC, id ASC",
            "support_asc": "support_count ASC, size ASC, id ASC",
            "size_desc": "size DESC, support_count DESC, id ASC",
            "size_asc": "size ASC, support_count DESC, id ASC",
        }
        order_sql = order_map.get(sort_by, "support_count DESC, size ASC, id ASC")

        total = conn.execute(
            f"SELECT COUNT(*) FROM frequent_itemsets WHERE {where_sql}",
            params,
        ).fetchone()[0]

        rows = conn.execute(
            f"""
            SELECT id, dataset, itemset_str, size, support_count, support_ratio
            FROM frequent_itemsets
            WHERE {where_sql}
            ORDER BY {order_sql}
            LIMIT ? OFFSET ?
            """,
            [*params, int(limit), int(offset)],
        ).fetchall()

        items = [
            {
                "id": r["id"],
                "dataset": r["dataset"],
                "itemset": r["itemset_str"],
                "items": [int(x) for x in r["itemset_str"].split()],
                "size": r["size"],
                "support_count": r["support_count"],
                "support_ratio": round(r["support_ratio"], 6),
            }
            for r in rows
        ]
        return {
            "total": int(total),
            "limit": int(limit),
            "offset": int(offset),
            "items": items,
        }
    finally:
        conn.close()


def query_association_rules(
    dataset: str = "full",
    antecedent_filter: str | None = None,
    consequent_filter: str | None = None,
    antecedent_size: int | None = None,
    consequent_size: int | None = None,
    min_confidence: float | None = None,
    min_lift: float | None = None,
    min_count: int | None = None,
    sort_by: str = "confidence_desc",
    limit: int = 50,
    offset: int = 0,
    db_path: Path | None = None,
) -> dict[str, Any]:
    conn = get_connection(db_path)
    try:
        clauses = ["dataset = ?"]
        params: list[Any] = [dataset]

        if antecedent_size is not None and antecedent_size > 0:
            clauses.append("antecedent_size = ?")
            params.append(int(antecedent_size))

        if consequent_size is not None and consequent_size > 0:
            clauses.append("consequent_size = ?")
            params.append(int(consequent_size))

        if min_confidence is not None and min_confidence > 0:
            clauses.append("confidence >= ?")
            params.append(float(min_confidence) - 1e-9)

        if min_lift is not None and min_lift > 0:
            clauses.append("lift >= ?")
            params.append(float(min_lift) - 1e-9)

        if min_count is not None and min_count > 0:
            clauses.append("support_count >= ?")
            params.append(int(min_count))

        if antecedent_filter:
            tokens = [t.strip() for t in antecedent_filter.replace(",", " ").split() if t.strip()]
            for tok in tokens:
                if tok.isdigit():
                    clauses.append("antecedent_padded LIKE ?")
                    params.append(f"% {int(tok)} %")

        if consequent_filter:
            tokens = [t.strip() for t in consequent_filter.replace(",", " ").split() if t.strip()]
            for tok in tokens:
                if tok.isdigit():
                    clauses.append("consequent_padded LIKE ?")
                    params.append(f"% {int(tok)} %")

        where_sql = " AND ".join(clauses)
        order_map = {
            "confidence_desc": "confidence DESC, lift DESC, support_count DESC, id ASC",
            "confidence_asc": "confidence ASC, support_count DESC, id ASC",
            "lift_desc": "lift DESC, confidence DESC, support_count DESC, id ASC",
            "support_desc": "support_count DESC, confidence DESC, id ASC",
        }
        order_sql = order_map.get(sort_by, "confidence_desc")
        if order_sql == "confidence_desc":
            order_sql = order_map["confidence_desc"]

        total = conn.execute(
            f"SELECT COUNT(*) FROM association_rules WHERE {where_sql}",
            params,
        ).fetchone()[0]

        rows = conn.execute(
            f"""
            SELECT id, dataset, antecedent_str, consequent_str,
                   antecedent_size, consequent_size,
                   support_count, support_ratio, confidence, lift
            FROM association_rules
            WHERE {where_sql}
            ORDER BY {order_sql}
            LIMIT ? OFFSET ?
            """,
            [*params, int(limit), int(offset)],
        ).fetchall()

        rules = [
            {
                "id": r["id"],
                "dataset": r["dataset"],
                "antecedent": r["antecedent_str"],
                "consequent": r["consequent_str"],
                "antecedent_items": [int(x) for x in r["antecedent_str"].split()],
                "consequent_items": [int(x) for x in r["consequent_str"].split()],
                "antecedent_size": r["antecedent_size"],
                "consequent_size": r["consequent_size"],
                "support_count": r["support_count"],
                "support_ratio": round(r["support_ratio"], 6),
                "confidence": round(r["confidence"], 6),
                "lift": round(r["lift"], 4),
            }
            for r in rows
        ]
        return {
            "total": int(total),
            "limit": int(limit),
            "offset": int(offset),
            "rules": rules,
        }
    finally:
        conn.close()


def recommend_for_basket(
    basket: list[int],
    dataset: str = "full",
    min_confidence: float = 0.6,
    top_k: int = 15,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """
    Find all association rules A -> C where A is a subset of the user's basket
    and C contains items not yet in the basket. Rank recommended items by confidence & lift.
    """
    basket_set = set(basket)
    if not basket_set:
        return {"basket": [], "recommendations": [], "matched_rules_count": 0, "matched_rules": []}

    conn = get_connection(db_path)
    try:
        # Candidate rules must have antecedent_size <= len(basket) and contain at least one item from basket
        or_clauses = ["antecedent_padded LIKE ?" for _ in basket_set]
        or_params = [f"% {item} %" for item in sorted(basket_set)]

        sql = f"""
            SELECT antecedent_str, consequent_str, antecedent_size, consequent_size,
                   support_count, support_ratio, confidence, lift
            FROM association_rules
            WHERE dataset = ?
              AND antecedent_size <= ?
              AND confidence >= ?
              AND ({' OR '.join(or_clauses)})
            ORDER BY confidence DESC, lift DESC, support_count DESC
        """
        rows = conn.execute(
            sql,
            [dataset, len(basket_set), float(min_confidence) - 1e-9, *or_params],
        ).fetchall()

        matched_rules: list[dict[str, Any]] = []
        item_scores: dict[int, dict[str, Any]] = {}

        for r in rows:
            ant_items = [int(x) for x in r["antecedent_str"].split()]
            if not set(ant_items).issubset(basket_set):
                continue
            cons_items = [int(x) for x in r["consequent_str"].split()]
            new_items = [x for x in cons_items if x not in basket_set]
            if not new_items:
                continue

            rule_obj = {
                "antecedent": r["antecedent_str"],
                "consequent": r["consequent_str"],
                "antecedent_items": ant_items,
                "consequent_items": cons_items,
                "new_items": new_items,
                "support_count": r["support_count"],
                "support_ratio": round(r["support_ratio"], 6),
                "confidence": round(r["confidence"], 6),
                "lift": round(r["lift"], 4),
            }
            matched_rules.append(rule_obj)

            for item_id in new_items:
                if item_id not in item_scores:
                    item_scores[item_id] = {
                        "item_id": item_id,
                        "max_confidence": r["confidence"],
                        "max_lift": r["lift"],
                        "max_support_count": r["support_count"],
                        "supporting_rules_count": 1,
                        "best_rule": f"{r['antecedent_str']} -> {r['consequent_str']}",
                        "best_antecedent": ant_items,
                    }
                else:
                    entry = item_scores[item_id]
                    entry["supporting_rules_count"] += 1
                    if r["confidence"] > entry["max_confidence"]:
                        entry["max_confidence"] = r["confidence"]
                        entry["best_rule"] = f"{r['antecedent_str']} -> {r['consequent_str']}"
                        entry["best_antecedent"] = ant_items
                    if r["lift"] > entry["max_lift"]:
                        entry["max_lift"] = r["lift"]
                    if r["support_count"] > entry["max_support_count"]:
                        entry["max_support_count"] = r["support_count"]

        recommendations = sorted(
            item_scores.values(),
            key=lambda x: (
                x["max_confidence"],
                x["max_lift"],
                x["supporting_rules_count"],
                x["max_support_count"],
            ),
            reverse=True,
        )[:top_k]

        for idx, rec in enumerate(recommendations, start=1):
            rec["rank"] = idx
            rec["max_confidence"] = round(rec["max_confidence"], 6)
            rec["max_lift"] = round(rec["max_lift"], 4)

        return {
            "dataset": dataset,
            "basket": sorted(basket_set),
            "matched_rules_count": len(matched_rules),
            "recommendations": recommendations,
            "matched_rules": matched_rules[:40],
        }
    finally:
        conn.close()


def query_benchmarks(db_path: Path | None = None) -> dict[str, Any]:
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM benchmarks ORDER BY experiment_type ASC, id ASC"
        ).fetchall()
        size_scaling = []
        support_scaling = []
        for r in rows:
            d = dict(r)
            d["details"] = json.loads(d.pop("details_json"))
            if d["experiment_type"] == "size_scaling":
                size_scaling.append(d)
            elif d["experiment_type"] == "support_scaling":
                support_scaling.append(d)
        return {
            "size_scaling": size_scaling,
            "support_scaling": support_scaling,
        }
    finally:
        conn.close()


def save_mining_run(
    source_type: str,
    dataset_label: str,
    telemetry: dict[str, Any],
    sample_itemsets: list[dict[str, Any]],
    sample_rules: list[dict[str, Any]],
    db_path: Path | None = None,
) -> int:
    conn = get_connection(db_path)
    try:
        with conn:
            cur = conn.execute(
                """
                INSERT INTO mining_runs (
                    created_at, source_type, dataset_label, n_transactions,
                    min_support, min_confidence, min_count, n_frequent, n_rules,
                    n_candidates_total, runtime_total_s, telemetry_json,
                    sample_itemsets_json, sample_rules_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    source_type,
                    dataset_label,
                    telemetry["n_transactions"],
                    telemetry["min_support"],
                    telemetry["min_confidence"],
                    telemetry["min_count"],
                    telemetry["n_frequent"],
                    telemetry["n_rules"],
                    telemetry["n_candidates_total"],
                    telemetry["timings"]["total_s"],
                    json.dumps(telemetry),
                    json.dumps(sample_itemsets),
                    json.dumps(sample_rules),
                ),
            )
            return int(cur.lastrowid)
    finally:
        conn.close()


def query_mining_runs(limit: int = 20, db_path: Path | None = None) -> list[dict[str, Any]]:
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM mining_runs ORDER BY id DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["telemetry"] = json.loads(d.pop("telemetry_json"))
            d["sample_itemsets"] = json.loads(d.pop("sample_itemsets_json"))
            d["sample_rules"] = json.loads(d.pop("sample_rules_json"))
            result.append(d)
        return result
    finally:
        conn.close()

