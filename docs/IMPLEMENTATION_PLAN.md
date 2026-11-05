# Phase 1 & Phase 2 Implementation Plan (`IMPLEMENTATION_PLAN.md`)

## 1. Technology Stack Selection

Based on the Task 3 requirements in `RC3_AI_Hackathon.docx` and the existing project environment (`Python 3.13`, `Node.js`):

| Layer | Selected Technology | Justification |
|---|---|---|
| **Core Mining Algorithm** | Python 3.13 + `numpy` (`uint64` Vertical Bitset Eclat + Hardware Popcount) | Complies 100% with Google Colab CPU constraints (`numpy`, `scipy`, `pandas`, `matplotlib` only). Processes $500,000$ transactions in $\approx 6\text{ seconds}$ using $< 250\text{ MB}$ RAM. |
| **Deliverable Notebook** | Jupyter Notebook (`Task3_Association_Rule_Mining.ipynb` & `Task_3.ipynb`) + `matplotlib` + `pandas` | Directly fulfills the hackathon submission rules with visible outputs, scaling plots, candidate pruning tables, and final timed cell. |
| **Backend Framework** | **FastAPI** + **Uvicorn** + **Pydantic v2** | High-performance async REST API with automatic OpenAPI/Swagger documentation, strict request validation, and static frontend serving. |
| **Database** | **SQLite 3** (`data/arm_analytics.db`) with indexed tables | Zero-configuration, serverless relational storage ideal for indexing $11,733+$ frequent itemsets, $110,402+$ rules, item statistics, benchmark measurements, and custom mining runs. |
| **Frontend Application** | **Modern Responsive HTML5 + CSS3 + Vanilla ES6+ JavaScript + Canvas Charts** | Fast, zero-build-fragility, modern dashboard served directly by FastAPI (and operable standalone) with interactive charts, live search/filtering, basket recommender, and live mining studio. |
| **Testing Framework** | **Pytest** + FastAPI/Starlette TestClient | Comprehensive automated unit, edge-case, ground-truth verification, database, and API integration tests. |

---

## 2. Project Directory Architecture

```text
C:\Users\DELL\Downloads\Hackton\Task3\
├── arm_task\                          # Preserved dataset files (dev + full transactions, params.json)
├── backend\
│   ├── __init__.py
│   ├── config.py                      # Environment-driven configuration & paths
│   ├── miner.py                       # Core Vertical-Bitset Eclat & Rule Generation Engine
│   ├── database.py                    # SQLite schema, connection manager, and query layer
│   ├── schemas.py                     # Pydantic v2 request/response validation schemas
│   ├── seed.py                        # Database seeding script (loads mined outputs & benchmarks)
│   └── main.py                        # FastAPI application & REST API endpoints
├── frontend\
│   ├── index.html                     # Responsive single-page analytics application
│   ├── styles.css                     # Modern dark/light glassmorphic data analytics UI styles
│   └── app.js                         # Complete API integration, interactive charts, recommender & live miner
├── notebooks\
│   └── generate_notebook.py           # Script that executes all stages, generates plots, and builds executed .ipynb
├── output\
│   ├── frequent_itemsets.csv          # Official full-dataset output deliverable (11,733 itemsets)
│   ├── rules.csv                      # Official full-dataset output deliverable (110,402 rules)
│   └── benchmarks.json                # Measured empirical scaling & support threshold telemetry
├── tests\
│   ├── test_miner.py                  # Unit, edge-case, and dev-set exact accuracy tests
│   └── test_api.py                    # Full backend API & database integration tests
├── docs\
│   ├── TASK3_REQUIREMENTS.md
│   ├── PROJECT_ANALYSIS.md
│   ├── IMPLEMENTATION_PLAN.md
│   ├── TESTING_REPORT.md
│   ├── MANUAL_SETUP.md
│   └── FINAL_DELIVERABLES.md
├── Task3_Association_Rule_Mining.ipynb # Primary executed Colab-ready hackathon deliverable notebook
├── Task_3.ipynb                       # Updated starter notebook with complete executed solution
├── frequent_itemsets.csv              # Root copy of full-dataset output deliverable for convenience
├── rules.csv                          # Root copy of full-dataset output deliverable for convenience
├── .env.example                       # Environment variable template
├── requirements.txt                   # Locked virtual environment dependencies
└── README.md                          # Complete setup, architecture, and usage documentation
```

---

## 3. Algorithmic Architecture: Vertical Bitset Eclat + Confidence-Pruned Rule Miner

### Stage 1: Transaction Parsing & CSR Flattening
- Read transaction lines and parse space-separated integers into a flat token array `flat` and transaction index array `tid`.
- Compute single-item supports in $O(N \cdot \bar{L})$ via `np.bincount(flat)`.
- Filter to frequent 1-itemsets $F_1 = \{i \in \mathcal{I} : \text{count}(\{i\}) \ge \text{min\_count}\}$.

### Stage 2: 64-Bit Vertical Bitset Construction & Equivalence Ordering
- Group occurrences of frequent items using a stable counting/radix sort (`np.argsort(flat, kind='stable')` + `np.searchsorted`).
- For each frequent item $i \in F_1$, pack its transaction ID list into a contiguous `uint64` bitset array of length $\lceil n / 64 \rceil$ words ($7,813$ `uint64` words $\approx 62.5\text{ KB}$ for $n = 500,000$).
- Sort $F_1$ in **ascending order of support count** (`cands.sort(key=lambda x: x[2])`). Intersecting sparser bitsets first drastically shrinks equivalence class sizes at deeper recursion levels ($k \ge 3$).

### Stage 3: Recursive Eclat Depth-First Search with Candidate Telemetry
- For each prefix itemset $P$ and its ordered equivalence class $[(i_1, B_1, c_1), \dots, (i_m, B_m, c_m)]$:
  - Record $P \cup \{i_r\}$ as frequent with count $c_r$.
  - For each subsequent item $i_s$ ($s > r$) in the equivalence class:
    - Increment `candidates_by_size[|P| + 2]`.
    - Compute bitset intersection $B_{rs} = B_r \mathbin{\&} B_s$ in vectorized C/SIMD speed.
    - Count support via hardware popcount (`np.bitwise_count(B_rs).sum()`).
    - If $\text{count}(B_{rs}) \ge \text{min\_count}$, append $(i_s, B_{rs}, \text{count}(B_{rs}))$ to the child equivalence class.
  - Recurse on non-empty child equivalence classes.

### Stage 4: Association Rule Enumeration & Anti-Monotone Confidence Pruning
- For every frequent itemset $X$ with $|X| = k \ge 2$ and support count $c = \text{count}(X)$:
  - Because $X$ is frequent, every non-empty subset $A \subset X$ is guaranteed by downward closure (Apriori property) to be in our frequent itemset dictionary `freq`.
  - A rule $A \Rightarrow (X \setminus A)$ has confidence $c / \text{count}(A) \ge \text{min\_confidence} \iff \text{count}(A) \le \lfloor c / \text{min\_confidence} \rfloor$.
  - Enumerate proper non-empty subsets $A \subset X$ ($2^k - 2$ masks; since $k \le 10$, $2^k - 2 \le 1022$), verify $c \ge \text{min\_confidence} \times \text{count}(A) - 10^{-12}$, and emit $(A, X \setminus A, c, c / \text{count}(A))$.

---

## 4. Database Schema (`data/arm_analytics.db`)

1. **`datasets`**: `name` (`dev` | `full`), `n_transactions`, `min_support`, `min_confidence`, `min_count`, `n_frequent`, `n_rules`, `avg_basket_len`, `max_basket_len`, `n_items_used`, `runtime_ms`, `stats_json`.
2. **`frequent_itemsets`**: `id`, `dataset`, `itemset_str`, `size`, `support_count`, `support_ratio` (indexed on `(dataset, size, support_count DESC)` and `(dataset, itemset_str)`).
3. **`association_rules`**: `id`, `dataset`, `antecedent_str`, `consequent_str`, `antecedent_size`, `consequent_size`, `support_count`, `support_ratio`, `confidence`, `lift` (indexed on `(dataset, confidence DESC, support_count DESC)` and `(dataset, antecedent_str)`).
4. **`benchmarks`**: `id`, `experiment_type` (`size_scaling` | `support_scaling`), `param_value`, `n_transactions`, `min_support`, `min_count`, `runtime_total_s`, `runtime_parse_s`, `runtime_mine_s`, `runtime_rules_s`, `n_candidates`, `n_frequent`, `n_rules`.
5. **`mining_runs`**: `id`, `created_at`, `dataset_source`, `n_transactions`, `min_support`, `min_confidence`, `min_count`, `n_frequent`, `n_rules`, `runtime_s`, `summary_json`.

