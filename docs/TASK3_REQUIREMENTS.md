# Task 3 Requirements Specification: Association Rule Mining at Scale

## 1. Problem Statement
Retailers, e-commerce platforms, and category managers rely on **Market Basket Analysis** (Association Rule Mining) to discover frequently co-purchased product combinations and high-confidence *"if a customer buys $A$, they also buy $C$"* association rules for shelf layout optimization, product bundling, and cart recommendation systems.

With $2,000$ distinct products across $500,000$ shopping transactions (with average basket length $\approx 11.27$ items and bulk orders reaching up to $74$ items), the combinatorial search space of $2^{2000}$ possible itemsets is intractably large for naive enumeration. A single large basket of size $74$ contains $2^{74} - 1 \approx 1.89 \times 10^{22}$ sub-combinations.

The objective of **Task 3 (Association Rule Mining at Scale — 20 Marks)** is to:
1. Design, implement, and verify an **exact, high-performance Association Rule Mining algorithm** (`mine`) using only the Python standard library, `numpy`, `scipy`, `pandas`, and `matplotlib` (no pre-built mining libraries or compiled add-ons) that finishes well within **15 minutes** and **12 GB RAM** on a single CPU runtime.
2. Achieve **100% exact agreement** ($0$ missing, $0$ extra, $0$ wrong entries) on both frequent itemsets and association rules against the development answer key (`dev_frequent_itemsets.csv`, `dev_rules.csv`) and the full $500,000$-transaction corpus (`transactions.txt`).
3. Provide rigorous **empirical scaling benchmarks and complexity analysis** across multiple dataset sizes ($N$) and support thresholds ($\text{min\_support}$), alongside candidate pruning metrics by itemset size $k$.
4. Provide a **Full-Stack Interactive Market Basket & Association Rule Mining Web Application** (FastAPI Backend + SQLite Database + Responsive Frontend Dashboard) that exposes the mining engine, dataset statistics, frequent itemsets explorer, association rules explorer, live basket recommendation simulator, custom mining runner, and empirical scaling benchmarks.

---

## 2. Target Users
1. **Hackathon Evaluators & Data Scientists**: Reviewing algorithmic correctness, vertical bitset Eclat pruning efficiency, candidate-vs-frequent counts per level $k$, and empirical complexity scaling in the Jupyter Notebook (`Task3_Association_Rule_Mining.ipynb`) and CSV outputs (`frequent_itemsets.csv`, `rules.csv`).
2. **Retail Merchandisers & Category Analysts**: Exploring frequent product bundles, filtering association rules by antecedent/consequent, confidence, lift, and support via the web dashboard.
3. **E-Commerce Engineers & Product Managers**: Testing real-time "Frequently Bought Together" cart recommendations and running custom association rule mining jobs with user-defined `min_support` and `min_confidence` thresholds.

---

## 3. Formal Definitions & Mathematical Specifications

- **Transaction Database ($\mathcal{T}$)**: A collection of $n$ transactions $T_1, T_2, \dots, T_n$, where each transaction $T_i \subseteq \mathcal{I}$ is a set of integer item IDs from item universe $\mathcal{I} = \{1, 2, \dots, 2000\}$.
- **Support Count ($\text{count}(X)$)**: For any non-empty itemset $X \subseteq \mathcal{I}$ ($|X| \ge 1$), $\text{count}(X)$ is the exact number of transactions containing every item in $X$:
  $$\text{count}(X) = \left|\{T_i \in \mathcal{T} : X \subseteq T_i\}\right|$$
- **Minimum Support Count ($\text{min\_count}$)**: Given relative threshold $\text{min\_support} = 0.003$:
  $$\text{min\_count} = \lceil \text{min\_support} \times n \rceil$$
  - For `dev_transactions.txt` ($n = 50,000$): $\text{min\_count} = \lceil 0.003 \times 50,000 \rceil = 150$.
  - For `transactions.txt` ($n = 500,000$): $\text{min\_count} = \lceil 0.003 \times 500,000 \rceil = 1,500$.
- **Frequent Itemset**: An itemset $X$ ($|X| \ge 1$) is frequent if and only if $\text{count}(X) \ge \text{min\_count}$.
- **Association Rule ($A \Rightarrow C$)**:
  - $A \neq \emptyset$, $C \neq \emptyset$, and $A \cap C = \emptyset$ (consequent $C$ may have any size $|C| \ge 1$).
  - $A \cup C$ must be a frequent itemset ($\text{count}(A \cup C) \ge \text{min\_count}$).
  - **Confidence**:
    $$\text{confidence}(A \Rightarrow C) = \frac{\text{count}(A \cup C)}{\text{count}(A)} \ge \text{min\_confidence} \quad (0.6)$$
  - **Lift** (computed for analytical enrichment in the web application and notebook insights):
    $$\text{lift}(A \Rightarrow C) = \frac{\text{confidence}(A \Rightarrow C)}{\text{count}(C) / n} = \frac{\text{count}(A \cup C) \times n}{\text{count}(A) \times \text{count}(C)}$$

---

## 4. Required Features

### 4.1 Core Algorithmic & Notebook Features (Hackathon Handout Source of Truth)
1. **Self-Contained `mine` Pipeline**:
   - Implements vertical bitset **Eclat (Equivalence Class Transformation)** depth-first search with uint64 bit-packed transaction ID lists and hardware popcount (`np.bitwise_count`), plus confidence-pruned rule generation.
   - Tracks exact telemetry: per-stage runtime (parsing/encoding, bitset construction, frequent itemset mining, rule generation), candidate count examined per itemset size $k$, and frequent count found per size $k$.
2. **Exact Output File Generation**:
   - `frequent_itemsets.csv`: Columns `itemset,count`, items space-separated and sorted ascending (e.g., `6 438,1048`), sorted deterministically by `(len(X), X)`, no duplicates.
   - `rules.csv`: Columns `antecedent,consequent,count,confidence`, items inside `antecedent` and `consequent` space-separated and sorted ascending, `count` = $\text{count}(A \cup C)$, `confidence` formatted to 6 decimal places (`f"{conf:.6f}"`), sorted deterministically by `(A, C)`, no duplicates.
3. **Dev-Set Exact Verification Report**:
   - Compares mined outputs on `dev_transactions.txt` against `dev_frequent_itemsets.csv` ($12,141$ itemsets) and `dev_rules.csv` ($125,999$ rules), reporting missing itemsets, extra itemsets, count mismatches, missing rules, extra rules, and confidence mismatches (all $0$).
4. **Candidate Pruning & Method Analysis**:
   - Detailed explanation of equivalence class clustering, ascending frequency ordering to minimize intermediate intersection sizes, and bitset intersection popcount.
   - Table and chart comparing candidates examined vs. frequent itemsets discovered across sizes $k = 1 \dots 10$.
5. **Empirical Complexity & Scaling Experiments**:
   - **Dataset Size Scaling ($N$)**: Runtime measured across at least 4 dataset sizes ($N \in \{25000, 50000, 100000, 250000, 500000\}$) with log-log polyfit slope analysis.
   - **Support Threshold Scaling ($\text{min\_support}$)**: Runtime, candidate count, frequent itemset count, and rule count measured across at least 3 support thresholds ($\text{min\_support} \in \{0.010, 0.006, 0.004, 0.003, 0.002\}$) with plots and stage breakdown analysis.

### 4.2 Full-Stack Web Application Features
1. **Analytics Overview Dashboard**:
   - Real-time KPI summary cards for both Full ($500,000$ tx) and Dev ($50,000$ tx) datasets (total transactions, unique items, frequent itemsets, association rules, execution time, average/max basket length).
   - Interactive charts: Frequent Itemsets & Candidates by Size $k$, Top Frequent Individual Items, Basket Length Distribution, and Rule Confidence vs. Support Scatter/Distribution.
2. **Frequent Itemsets Explorer**:
   - Filterable, sortable, paginated table of mined frequent itemsets from the database.
   - Filter by dataset (`full` or `dev`), itemset size $k$, minimum count/support, and contained item ID(s).
   - Direct CSV export.
3. **Association Rules Explorer**:
   - Filterable, sortable, paginated table of mined association rules ($A \Rightarrow C$) with support count, support %, confidence, and lift.
   - Filter by antecedent item(s), consequent item(s), minimum confidence, minimum lift, antecedent/consequent size, and dataset.
   - Direct CSV export.
4. **Smart Basket Recommender ("Frequently Bought Together" Simulator)**:
   - Interactive shopping cart builder where users select or enter item IDs currently in a customer's basket.
   - Queries all matching association rules whose antecedent $A \subseteq \text{Basket}$ and ranks recommended consequent items $C \setminus \text{Basket}$ by confidence, lift, and support count, showing exact supporting rules.
5. **Live Custom Mining Studio**:
   - Run the vertical-bitset Eclat miner in real time on either a configurable slice of the dataset or user-pasted/uploaded transaction lines with custom `min_support` and `min_confidence` validation.
   - Saves mining job runs to SQLite and displays live stage timings, candidate pruning table, discovered itemsets, and generated rules.
6. **Complexity & Scaling Benchmark Viewer**:
   - Displays the actual measured scaling benchmarks (runtime vs. transaction count $N$ with log-log slope, runtime/candidates vs. $\text{min\_support}$, and per-stage bottleneck breakdown).

---

## 5. Functional Requirements
- **FR-01**: Load transaction files (`dev_transactions.txt`, `transactions.txt`) accurately where each line contains space-separated integer item IDs.
- **FR-02**: Compute $\text{min\_count} = \lceil \text{min\_support} \times n \rceil$ and identify all itemsets $X$ ($|X| \ge 1$) with $\text{count}(X) \ge \text{min\_count}$.
- **FR-03**: Generate all association rules $A \Rightarrow C$ ($A, C \neq \emptyset$, $A \cap C = \emptyset$) from frequent itemsets where $\text{count}(A \cup C) / \text{count}(A) \ge \text{min\_confidence} - 10^{-12}$.
- **FR-04**: Export `frequent_itemsets.csv` and `rules.csv` matching the exact schema, sorting, and formatting of the hackathon specification.
- **FR-05**: Provide RESTful backend API endpoints (`/api/health`, `/api/stats`, `/api/itemsets`, `/api/rules`, `/api/recommend`, `/api/mine`, `/api/benchmarks`, `/api/runs`, `/api/export/{type}`) with strict input validation and error handling.
- **FR-06**: Persist datasets metadata, frequent itemsets, association rules, complexity benchmarks, and custom mining runs in a relational SQLite database with reproducible seeding.

---

## 6. Non-Functional Requirements
- **NFR-01 (Performance)**: Full pipeline on $500,000$ transactions at $\text{min\_support} = 0.003$, $\text{min\_confidence} = 0.6$ must complete in $< 15$ seconds locally (well under the 15-minute Colab limit). API queries must respond in $< 200\text{ ms}$.
- **NFR-02 (Memory Efficiency)**: Peak memory usage during $500,000$-transaction mining must remain $< 500\text{ MB}$ (well under the 12 GB Colab limit) using packed 64-bit integer bitsets ($\approx 62.5\text{ KB}$ per frequent 1-itemset for $n = 500,000$).
- **NFR-03 (Algorithmic Purity)**: Core mining engine uses only Python standard library + `numpy` (no `mlxtend`, `apyori`, `numba`, or `Cython`), and never reads private answer keys (`frequent_itemsets.csv`, `rules.csv`) during mining.
- **NFR-04 (Security & Config)**: Environment-driven configuration (`.env` / `config.py`), zero hardcoded secrets, full input validation on all API endpoints.
- **NFR-05 (Responsiveness & UX)**: Clean, responsive modern dashboard supporting desktop and mobile viewports with loading states, empty states, and clear error feedback.

---

## 7. Expected Inputs and Outputs

### Inputs
| File / Input | Size / Rows | Format | Description |
|---|---|---|---|
| `transactions.txt` | $500,000$ lines | Space-separated ints | Full transaction corpus ($2,000$ distinct items, avg len $11.27$, max len $74$) |
| `dev_transactions.txt` | $50,000$ lines | Space-separated ints | Development transaction corpus ($2,000$ distinct items, avg len $11.29$, max len $72$) |
| `dev_frequent_itemsets.csv` | $12,141$ rows | `itemset,count` | Official dev ground-truth frequent itemsets for verification |
| `dev_rules.csv` | $125,999$ rows | `antecedent,consequent,count,confidence` | Official dev ground-truth association rules for verification |
| `params.json` | 1 JSON object | `{"min_support": 0.003, "min_confidence": 0.6}` | Official mining thresholds |

### Outputs
| File / Output | Rows (Full Dataset) | Schema | Description |
|---|---|---|---|
| `frequent_itemsets.csv` | $11,733$ rows | `itemset,count` | Exact frequent itemsets on `transactions.txt` |
| `rules.csv` | $110,402$ rows | `antecedent,consequent,count,confidence` | Exact association rules on `transactions.txt` |
| `Task3_Association_Rule_Mining.ipynb` | Complete Notebook | `.ipynb` with outputs | Executed Colab-ready notebook with all 5 deliverables |

---

## 8. Evaluation Criteria (from `RC3_AI_Hackathon.docx` Matrix)
| # | Parameter | Weight | Marks (out of 20) | What Evaluators Look For |
|---|---|---|---|---|
| 1 | Problem understanding & planning | 15% | 3 | Goal, inputs, outputs, rules, and constraints understood; work planned in stages. |
| 2 | Approach and method | 25% | 5 | Well-chosen method of our own (Vertical Bitset Eclat + Pruned Rule Generator) with justified design & candidate table. |
| 3 | Correctness, completeness & performance | 30% | 6 | Exact match for itemsets, counts, rules, and confidences within 15 min / 12 GB budget. |
| 4 | Testing, review & robustness | 20% | 4 | Dev-set verification ($0$ errors), edge-case handling, scaling verification. |
| 5 | Evidence and reporting | 10% | 2 | Complete notebook, honest timings, scaling plots, complexity analysis, and documentation. |

---

## 9. Expected Final Deliverables
1. `Task3_Association_Rule_Mining.ipynb` (and updated `Task_3.ipynb`) — Complete, executed Jupyter Notebook with visible outputs, plots, tables, complexity analysis, and final timed cell.
2. `frequent_itemsets.csv` & `rules.csv` — Generated from the full $500,000$-transaction dataset.
3. Full-Stack Web Application (`backend/`, `frontend/`, `app.py`, `database/`) with SQLite database and REST API.
4. Comprehensive Automated Test Suite (`tests/`) covering unit, edge-case, dev-set accuracy, database, and API integration tests.
5. Complete Documentation Suite (`README.md`, `docs/TASK3_REQUIREMENTS.md`, `docs/PROJECT_ANALYSIS.md`, `docs/IMPLEMENTATION_PLAN.md`, `docs/TESTING_REPORT.md`, `docs/MANUAL_SETUP.md`, `docs/FINAL_DELIVERABLES.md`).

