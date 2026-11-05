"""
Complete Backend API, Database, Validation, Error Handling, and E2E Workflow Tests (`tests/test_api.py`).

Uses Starlette ASGI lifespan / raw ASGI client invocation to test every route,
query parameter, valid/invalid/empty payload, and database persistence.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any
from urllib.parse import urlencode

import pytest

from backend.main import app


def call_asgi(
    method: str,
    path: str,
    query_params: dict[str, Any] | None = None,
    json_body: Any = None,
    raw_body: bytes | None = None,
) -> tuple[int, dict[str, str], bytes]:
    """Synchronous helper to invoke the Starlette ASGI app directly in tests."""
    query_string = urlencode(query_params or {}).encode("utf-8")
    headers = [(b"host", b"testserver")]
    body_bytes = b""
    if json_body is not None:
        body_bytes = json.dumps(json_body).encode("utf-8")
        headers.append((b"content-type", b"application/json"))
    elif raw_body is not None:
        body_bytes = raw_body
        headers.append((b"content-type", b"application/json"))

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method.upper(),
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": query_string,
        "headers": headers,
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    }

    messages: list[dict[str, Any]] = []
    body_sent = False

    async def receive() -> dict[str, Any]:
        nonlocal body_sent
        if not body_sent:
            body_sent = True
            return {"type": "http.request", "body": body_bytes, "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message: dict[str, Any]) -> None:
        messages.append(message)

    coro = app(scope, receive, send)
    try:
        while True:
            coro.send(None)
    except StopIteration:
        pass

    start_msg = next(m for m in messages if m["type"] == "http.response.start")
    status_code = start_msg["status"]
    resp_headers = {
        k.decode("latin1").lower(): v.decode("latin1") for k, v in start_msg.get("headers", [])
    }
    resp_body = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body")
    return status_code, resp_headers, resp_body


def test_health_endpoint():
    status, _, body = call_asgi("GET", "/api/health")
    assert status == 200
    data = json.loads(body)
    assert data["status"] == "ok"
    assert data["database_connected"] is True
    assert data["datasets_loaded"] == 2
    assert data["total_frequent_itemsets_indexed"] == 12141 + 11733
    assert data["total_association_rules_indexed"] == 125999 + 110402
    assert data["deliverables_ready"] is True


def test_frontend_static_routes():
    status_idx, headers_idx, body_idx = call_asgi("GET", "/")
    assert status_idx == 200
    assert "text/html" in headers_idx["content-type"]
    assert b"Association Rule Mining at Scale" in body_idx

    status_css, headers_css, body_css = call_asgi("GET", "/styles.css")
    assert status_css == 200
    assert "text/css" in headers_css["content-type"]
    assert b"--bg-base" in body_css

    status_js, headers_js, body_js = call_asgi("GET", "/app.js")
    assert status_js == 200
    assert "javascript" in headers_js["content-type"]
    assert b"loadFrequentItemsets" in body_js

    status_404, _, _ = call_asgi("GET", "/nonexistent_asset.js")
    assert status_404 == 404


def test_stats_endpoint():
    status, _, body = call_asgi("GET", "/api/stats")
    assert status == 200
    data = json.loads(body)
    assert data["status"] == "ok"
    assert "full" in data["datasets"]
    assert "dev" in data["datasets"]
    assert data["datasets"]["full"]["n_transactions"] == 500000
    assert data["datasets"]["full"]["n_frequent"] == 11733
    assert data["datasets"]["full"]["n_rules"] == 110402
    assert data["datasets"]["dev"]["n_transactions"] == 50000
    assert data["datasets"]["dev"]["n_frequent"] == 12141
    assert data["datasets"]["dev"]["n_rules"] == 125999


def test_itemsets_endpoint_valid_and_filtered():
    # Default full dataset query
    status, _, body = call_asgi("GET", "/api/itemsets", {"dataset": "full", "limit": 10})
    assert status == 200
    data = json.loads(body)
    assert data["total"] == 11733
    assert len(data["items"]) == 10

    # Filter by size k=1 on dev set -> 388 frequent 1-itemsets
    status2, _, body2 = call_asgi("GET", "/api/itemsets", {"dataset": "dev", "size": 1, "limit": 20})
    assert status2 == 200
    data2 = json.loads(body2)
    assert data2["total"] == 388
    assert all(item["size"] == 1 for item in data2["items"])

    # Filter by item ID '10'
    status3, _, body3 = call_asgi(
        "GET", "/api/itemsets", {"dataset": "dev", "item_filter": "10", "limit": 15}
    )
    assert status3 == 200
    data3 = json.loads(body3)
    assert data3["total"] > 0
    assert all(10 in item["items"] for item in data3["items"])


def test_itemsets_endpoint_invalid_inputs():
    # Invalid dataset
    s1, _, _ = call_asgi("GET", "/api/itemsets", {"dataset": "invalid_ds"})
    assert s1 == 400

    # Out-of-bounds size
    s2, _, _ = call_asgi("GET", "/api/itemsets", {"size": 99})
    assert s2 == 400

    # Non-integer size
    s3, _, _ = call_asgi("GET", "/api/itemsets", {"size": "abc"})
    assert s3 == 400

    # Invalid item_filter with alphabetic text
    s4, _, _ = call_asgi("GET", "/api/itemsets", {"item_filter": "item_xyz"})
    assert s4 == 400


def test_rules_endpoint_valid_and_filtered():
    status, _, body = call_asgi(
        "GET",
        "/api/rules",
        {
            "dataset": "full",
            "antecedent_filter": "6",
            "min_confidence": 0.6,
            "sort_by": "confidence_desc",
            "limit": 15,
        },
    )
    assert status == 200
    data = json.loads(body)
    assert data["total"] > 0
    for rule in data["rules"]:
        assert 6 in rule["antecedent_items"]
        assert rule["confidence"] >= 0.6

    # Filter by consequent_size = 2
    status2, _, body2 = call_asgi(
        "GET",
        "/api/rules",
        {"dataset": "dev", "consequent_size": 2, "limit": 10},
    )
    assert status2 == 200
    data2 = json.loads(body2)
    assert data2["total"] > 0
    assert all(r["consequent_size"] == 2 for r in data2["rules"])


def test_rules_endpoint_invalid_inputs():
    s1, _, _ = call_asgi("GET", "/api/rules", {"min_confidence": 1.5})
    assert s1 == 400

    s2, _, _ = call_asgi("GET", "/api/rules", {"min_lift": -2.0})
    assert s2 == 400

    s3, _, _ = call_asgi("GET", "/api/rules", {"antecedent_filter": "bad_token"})
    assert s3 == 400


def test_basket_recommendation_endpoint_valid_and_invalid():
    # Valid basket [6, 799]
    status, _, body = call_asgi(
        "POST",
        "/api/recommend",
        json_body={
            "dataset": "dev",
            "basket": [6, 799],
            "min_confidence": 0.6,
            "top_k": 10,
        },
    )
    assert status == 200
    data = json.loads(body)
    assert data["status"] == "ok"
    assert data["matched_rules_count"] > 0
    assert len(data["recommendations"]) > 0
    # Recommended items must not already be in the basket [6, 799]
    for rec in data["recommendations"]:
        assert rec["item_id"] not in (6, 799)

    # Empty basket -> 422 validation error
    s_empty, _, _ = call_asgi(
        "POST",
        "/api/recommend",
        json_body={"dataset": "full", "basket": [], "min_confidence": 0.6},
    )
    assert s_empty == 422

    # Malformed JSON -> 400
    s_bad_json, _, _ = call_asgi("POST", "/api/recommend", raw_body=b"{not_valid_json")
    assert s_bad_json == 400


def test_live_mine_endpoint_preset_and_custom_and_invalid():
    # 1. Custom pasted transactions
    custom_tx = "\n".join(
        [
            "10 20 30 40",
            "10 20 30",
            "10 20 30 50",
            "10 20 40",
            "10 20 30 40 50",
            "20 30 40",
        ]
    )
    status, _, body = call_asgi(
        "POST",
        "/api/mine",
        json_body={
            "source_type": "custom",
            "custom_transactions_text": custom_tx,
            "min_support": 0.5,
            "min_confidence": 0.7,
            "top_limit": 20,
        },
    )
    assert status == 200
    data = json.loads(body)
    assert data["status"] == "ok"
    assert data["run_id"] >= 1
    assert data["telemetry"]["n_transactions"] == 6
    assert data["telemetry"]["n_frequent"] > 0
    assert data["telemetry"]["n_rules"] > 0

    # 2. Preset slice (1,000 dev transactions)
    status2, _, body2 = call_asgi(
        "POST",
        "/api/mine",
        json_body={
            "source_type": "preset",
            "dataset": "dev",
            "max_transactions": 1000,
            "min_support": 0.01,
            "min_confidence": 0.6,
            "top_limit": 20,
        },
    )
    assert status2 == 200
    data2 = json.loads(body2)
    assert data2["telemetry"]["n_transactions"] == 1000

    # 3. Empty custom transactions -> 400
    s_empty, _, _ = call_asgi(
        "POST",
        "/api/mine",
        json_body={
            "source_type": "custom",
            "custom_transactions_text": "   ",
            "min_support": 0.5,
            "min_confidence": 0.6,
        },
    )
    assert s_empty == 400

    # 4. Non-integer item in custom transactions -> 400
    s_non_int, _, _ = call_asgi(
        "POST",
        "/api/mine",
        json_body={
            "source_type": "custom",
            "custom_transactions_text": "10 20 abc\n10 20",
            "min_support": 0.5,
            "min_confidence": 0.6,
        },
    )
    assert s_non_int == 400


def test_benchmarks_runs_and_export_endpoints():
    s_bench, _, b_bench = call_asgi("GET", "/api/benchmarks")
    assert s_bench == 200
    bench = json.loads(b_bench)
    assert len(bench["size_scaling"]) == 5
    assert len(bench["support_scaling"]) == 5

    s_runs, _, b_runs = call_asgi("GET", "/api/runs")
    assert s_runs == 200
    runs = json.loads(b_runs)
    assert len(runs["runs"]) >= 1

    s_exp1, h_exp1, b_exp1 = call_asgi("GET", "/api/export/frequent_itemsets")
    assert s_exp1 == 200
    assert "text/csv" in h_exp1["content-type"]
    assert b"itemset,count" in b_exp1[:50]

    s_exp2, h_exp2, b_exp2 = call_asgi("GET", "/api/export/rules")
    assert s_exp2 == 200
    assert "text/csv" in h_exp2["content-type"]
    assert b"antecedent,consequent,count,confidence" in b_exp2[:80]

    s_exp_bad, _, _ = call_asgi("GET", "/api/export/unknown_file")
    assert s_exp_bad == 404

