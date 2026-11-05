"""
Task 3 Backend REST API & Static Web Server (`backend/main.py`).

Built on Starlette + Pydantic v2 + SQLite + NumPy Vertical-Bitset Eclat Miner.
Provides complete REST endpoints for dataset analytics, frequent itemsets search,
association rules search, smart basket recommendations, live custom transaction mining,
empirical complexity benchmarks, and CSV deliverable exports.
"""
from __future__ import annotations

import csv
import io
import json
import logging
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from starlette.routing import Route

from backend.config import APP_HOST, APP_PORT, DATA_DIR, DB_PATH, FRONTEND_DIR, OUTPUT_DIR
from backend.database import (
    get_connection,
    init_db,
    query_association_rules,
    query_benchmarks,
    query_datasets_overview,
    query_frequent_itemsets,
    query_mining_runs,
    recommend_for_basket,
    save_mining_run,
)
from backend.miner import load_transactions, mine
from backend.schemas import BasketRecommendationRequest, CustomMineRequest

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("task3.api")

# Cache loaded preset transaction lists for fast interactive custom slice mining
_TX_CACHE: dict[str, list[list[int]]] = {}


def _get_preset_transactions(dataset: str) -> list[list[int]]:
    if dataset not in _TX_CACHE:
        filename = "dev_transactions.txt" if dataset == "dev" else "transactions.txt"
        _TX_CACHE[dataset] = load_transactions(DATA_DIR / filename)
    return _TX_CACHE[dataset]


def _error_response(message: str, status_code: int = 400, details: Any = None) -> JSONResponse:
    payload: dict[str, Any] = {"status": "error", "message": message}
    if details is not None:
        payload["details"] = details
    return JSONResponse(payload, status_code=status_code)


async def health_endpoint(request: Request) -> JSONResponse:
    try:
        conn = get_connection()
        try:
            fi_count = conn.execute("SELECT COUNT(*) FROM frequent_itemsets").fetchone()[0]
            ar_count = conn.execute("SELECT COUNT(*) FROM association_rules").fetchone()[0]
            ds_count = conn.execute("SELECT COUNT(*) FROM datasets").fetchone()[0]
        finally:
            conn.close()
        return JSONResponse(
            {
                "status": "ok",
                "service": "Task 3 — Association Rule Mining at Scale API",
                "database_connected": True,
                "datasets_loaded": int(ds_count),
                "total_frequent_itemsets_indexed": int(fi_count),
                "total_association_rules_indexed": int(ar_count),
                "deliverables_ready": (OUTPUT_DIR / "frequent_itemsets.csv").is_file()
                and (OUTPUT_DIR / "rules.csv").is_file(),
            }
        )
    except Exception as exc:
        logger.exception("Health check failed")
        return _error_response(f"Database check failed: {exc}", status_code=500)


async def stats_endpoint(request: Request) -> JSONResponse:
    try:
        datasets = query_datasets_overview()
        if not datasets:
            return _error_response(
                "Database is empty. Run `python -m backend.seed` first.",
                status_code=503,
            )
        return JSONResponse({"status": "ok", "datasets": datasets})
    except Exception as exc:
        logger.exception("Stats endpoint error")
        return _error_response(str(exc), status_code=500)


async def itemsets_endpoint(request: Request) -> JSONResponse:
    qp = request.query_params
    dataset = qp.get("dataset", "full").strip().lower()
    if dataset not in ("full", "dev"):
        return _error_response("Invalid dataset parameter. Must be 'full' or 'dev'.", 400)

    try:
        size = int(qp["size"]) if qp.get("size") not in (None, "", "all") else None
        if size is not None and (size < 1 or size > 20):
            return _error_response("size must be between 1 and 20.", 400)

        min_count = int(qp["min_count"]) if qp.get("min_count") not in (None, "") else None
        if min_count is not None and min_count < 1:
            return _error_response("min_count must be >= 1.", 400)

        limit = int(qp.get("limit", "50"))
        offset = int(qp.get("offset", "0"))
        if limit < 1 or limit > 500 or offset < 0:
            return _error_response("limit must be 1..500 and offset >= 0.", 400)
    except ValueError:
        return _error_response("Numeric query parameters (size, min_count, limit, offset) must be integers.", 400)

    item_filter = qp.get("item_filter", "").strip()
    if item_filter:
        tokens = [t.strip() for t in item_filter.replace(",", " ").split() if t.strip()]
        if any((not t.isdigit()) or int(t) <= 0 for t in tokens):
            return _error_response("item_filter must contain positive integer item IDs separated by spaces or commas.", 400)

    sort_by = qp.get("sort_by", "support_desc")
    data = query_frequent_itemsets(
        dataset=dataset,
        size=size,
        min_count=min_count,
        item_filter=item_filter or None,
        sort_by=sort_by,
        limit=limit,
        offset=offset,
    )
    return JSONResponse({"status": "ok", **data})


async def rules_endpoint(request: Request) -> JSONResponse:
    qp = request.query_params
    dataset = qp.get("dataset", "full").strip().lower()
    if dataset not in ("full", "dev"):
        return _error_response("Invalid dataset parameter. Must be 'full' or 'dev'.", 400)

    try:
        antecedent_size = (
            int(qp["antecedent_size"])
            if qp.get("antecedent_size") not in (None, "", "all")
            else None
        )
        consequent_size = (
            int(qp["consequent_size"])
            if qp.get("consequent_size") not in (None, "", "all")
            else None
        )
        min_confidence = (
            float(qp["min_confidence"])
            if qp.get("min_confidence") not in (None, "")
            else None
        )
        min_lift = (
            float(qp["min_lift"])
            if qp.get("min_lift") not in (None, "")
            else None
        )
        min_count = (
            int(qp["min_count"])
            if qp.get("min_count") not in (None, "")
            else None
        )
        limit = int(qp.get("limit", "50"))
        offset = int(qp.get("offset", "0"))
    except ValueError:
        return _error_response("Invalid numeric filter parameter in query string.", 400)

    if min_confidence is not None and not (0.0 < min_confidence <= 1.0):
        return _error_response("min_confidence must be between 0.0 and 1.0.", 400)
    if min_lift is not None and min_lift < 0.0:
        return _error_response("min_lift must be non-negative.", 400)
    if limit < 1 or limit > 500 or offset < 0:
        return _error_response("limit must be 1..500 and offset >= 0.", 400)

    antecedent_filter = qp.get("antecedent_filter", "").strip()
    consequent_filter = qp.get("consequent_filter", "").strip()
    for label, flt in (("antecedent_filter", antecedent_filter), ("consequent_filter", consequent_filter)):
        if flt:
            tokens = [t.strip() for t in flt.replace(",", " ").split() if t.strip()]
            if any((not t.isdigit()) or int(t) <= 0 for t in tokens):
                return _error_response(f"{label} must contain positive integer item IDs.", 400)

    sort_by = qp.get("sort_by", "confidence_desc")
    data = query_association_rules(
        dataset=dataset,
        antecedent_filter=antecedent_filter or None,
        consequent_filter=consequent_filter or None,
        antecedent_size=antecedent_size,
        consequent_size=consequent_size,
        min_confidence=min_confidence,
        min_lift=min_lift,
        min_count=min_count,
        sort_by=sort_by,
        limit=limit,
        offset=offset,
    )
    return JSONResponse({"status": "ok", **data})


async def recommend_endpoint(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        return _error_response("Request body must be valid JSON.", 400)

    try:
        req = BasketRecommendationRequest(**body)
    except ValidationError as exc:
        return _error_response("Invalid basket recommendation request.", 422, exc.errors())

    result = recommend_for_basket(
        basket=req.basket,
        dataset=req.dataset,
        min_confidence=req.min_confidence,
        top_k=req.top_k,
    )
    return JSONResponse({"status": "ok", **result})


async def live_mine_endpoint(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        return _error_response("Request body must be valid JSON.", 400)

    try:
        req = CustomMineRequest(**body)
    except ValidationError as exc:
        return _error_response("Invalid mining configuration.", 422, exc.errors())

    if req.source_type == "custom":
        raw_text = (req.custom_transactions_text or "").strip()
        if not raw_text:
            return _error_response("custom_transactions_text cannot be empty when source_type='custom'.", 400)
        tx: list[list[int]] = []
        for idx, line in enumerate(raw_text.splitlines(), start=1):
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            tokens = s.replace(",", " ").split()
            try:
                items = sorted({int(tok) for tok in tokens})
            except ValueError:
                return _error_response(
                    f"Line {idx} contains non-integer item ID: '{s}'. Provide space-separated positive integers.",
                    400,
                )
            if any(x <= 0 for x in items):
                return _error_response(f"Line {idx} contains non-positive item ID.", 400)
            if items:
                tx.append(items)
        if len(tx) < 2:
            return _error_response("Please provide at least 2 valid transactions for custom mining.", 400)
        dataset_label = f"Custom ({len(tx):,} transactions)"
    else:
        all_tx = _get_preset_transactions(req.dataset)
        n_use = min(req.max_transactions, len(all_tx))
        tx = all_tx[:n_use]
        dataset_label = f"{req.dataset.upper()} Slice ({n_use:,} transactions)"

    freq, rules, telemetry = mine(
        tx,
        min_support=req.min_support,
        min_confidence=req.min_confidence,
        return_telemetry=True,
    )

    n = telemetry["n_transactions"]
    sample_itemsets = [
        {
            "itemset": " ".join(map(str, X)),
            "items": list(X),
            "size": len(X),
            "count": count,
            "support_ratio": round(count / n, 6) if n > 0 else 0.0,
        }
        for X, count in sorted(freq.items(), key=lambda kv: (-kv[1], -len(kv[0]), kv[0]))[: req.top_limit]
    ]

    sample_rules = []
    for A, C, count, conf in sorted(rules, key=lambda r: (-r[3], -r[2], r[0]))[: req.top_limit]:
        cons_count = freq.get(C, 1)
        lift = (conf * n) / cons_count if cons_count > 0 else 0.0
        sample_rules.append(
            {
                "antecedent": " ".join(map(str, A)),
                "consequent": " ".join(map(str, C)),
                "antecedent_items": list(A),
                "consequent_items": list(C),
                "count": count,
                "support_ratio": round(count / n, 6) if n > 0 else 0.0,
                "confidence": round(conf, 6),
                "lift": round(lift, 4),
            }
        )

    run_id = save_mining_run(
        source_type=req.source_type,
        dataset_label=dataset_label,
        telemetry=telemetry,
        sample_itemsets=sample_itemsets[:30],
        sample_rules=sample_rules[:30],
    )

    return JSONResponse(
        {
            "status": "ok",
            "run_id": run_id,
            "dataset_label": dataset_label,
            "telemetry": telemetry,
            "itemsets": sample_itemsets,
            "rules": sample_rules,
        }
    )


async def benchmarks_endpoint(request: Request) -> JSONResponse:
    data = query_benchmarks()
    return JSONResponse({"status": "ok", **data})


async def runs_endpoint(request: Request) -> JSONResponse:
    runs = query_mining_runs(limit=20)
    return JSONResponse({"status": "ok", "runs": runs})


async def export_endpoint(request: Request) -> Response:
    export_type = request.path_params.get("export_type", "")
    file_map = {
        "frequent_itemsets": OUTPUT_DIR / "frequent_itemsets.csv",
        "rules": OUTPUT_DIR / "rules.csv",
        "dev_frequent_itemsets": OUTPUT_DIR / "dev_frequent_itemsets.csv",
        "dev_rules": OUTPUT_DIR / "dev_rules.csv",
    }
    target = file_map.get(export_type)
    if target is None:
        return _error_response(
            "Invalid export_type. Choose from: frequent_itemsets, rules, dev_frequent_itemsets, dev_rules.",
            404,
        )
    if not target.is_file():
        return _error_response(f"Export file {target.name} not found.", 404)
    return Response(
        content=target.read_bytes(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{target.name}"'},
    )


async def index_page(request: Request) -> Response:
    index_file = FRONTEND_DIR / "index.html"
    if not index_file.is_file():
        return HTMLResponse("<h1>Frontend not built yet</h1>", status_code=404)
    return HTMLResponse(index_file.read_text(encoding="utf-8"))


async def frontend_asset(request: Request) -> Response:
    asset_name = request.path_params.get("asset_name", "")
    safe_map = {
        "styles.css": ("text/css; charset=utf-8", FRONTEND_DIR / "styles.css"),
        "app.js": ("application/javascript; charset=utf-8", FRONTEND_DIR / "app.js"),
    }
    if asset_name not in safe_map:
        return _error_response("Asset not found", 404)
    mime, path = safe_map[asset_name]
    if not path.is_file():
        return _error_response("Asset file missing", 404)
    return Response(content=path.read_bytes(), media_type=mime)


routes = [
    Route("/", index_page, methods=["GET"]),
    Route("/api/health", health_endpoint, methods=["GET"]),
    Route("/api/stats", stats_endpoint, methods=["GET"]),
    Route("/api/itemsets", itemsets_endpoint, methods=["GET"]),
    Route("/api/rules", rules_endpoint, methods=["GET"]),
    Route("/api/recommend", recommend_endpoint, methods=["POST"]),
    Route("/api/mine", live_mine_endpoint, methods=["POST"]),
    Route("/api/benchmarks", benchmarks_endpoint, methods=["GET"]),
    Route("/api/runs", runs_endpoint, methods=["GET"]),
    Route("/api/export/{export_type}", export_endpoint, methods=["GET"]),
    Route("/{asset_name}", frontend_asset, methods=["GET"]),
]

middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
]

app = Starlette(debug=False, routes=routes, middleware=middleware)

