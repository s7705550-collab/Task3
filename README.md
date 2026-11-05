# Task 3 — Association Rule Mining at Scale (`RC3 AI Hackathon`)

A complete, high-performance **Association Rule Mining at Scale** engine, executed Google Colab Jupyter Notebook deliverable, and full-stack **Market Basket Analytics Web Application** built for **Task 3 (20 Marks)** of the RC3 AI Hackathon.

---

## 1. Project Overview

Retailers and e-commerce platforms process hundreds of thousands of customer shopping baskets across thousands of products to uncover frequently co-purchased item combinations and high-confidence association rules ($A \Rightarrow C$: *"if a customer buys $A$, they also buy $C$"*).

This project delivers:
1. **Pure-NumPy `uint64` Vertical-Bitset Eclat + Pruned Rule Mining Engine** ([`backend/miner.py`](file:///C:/Users/DELL/Downloads/Hackton/Task3/backend/miner.py)):
   - Uses **only** the Python standard library and `numpy` (no `mlxtend`, `apyori`, `numba`, or `Cython`), complying 100% with the Google Colab CPU rules in `RC3_AI_Hackathon.docx`.
   - Processes the **$50,000$-transaction Dev Set** in **$1.582\text{ seconds}$**, recovering all **$12,141$ frequent itemsets** and **$125,999$ association rules** with **0 missing, 0 extra, and 0 wrong entries** against `dev_frequent_itemsets.csv` and `dev_rules.csv`.
   - Processes the **$500,000$-transaction Full Corpus** (`transactions.txt`) in **$5.367\text{ seconds}$** ($< 1\%$ of the 15-minute budget and $< 250\text{ MB}$ of the 12 GB RAM limit), discovering **$11,733$ frequent itemsets** and **$110,402$ association rules**.
2. **Executed Colab-Ready Jupyter Notebook & CSV Deliverables**:
   - [`Task3_Association_Rule_Mining.ipynb`](file:///C:/Users/DELL/Downloads/Hackton/Task3/Task3_Association_Rule_Mining.ipynb) (and updated [`Task_3.ipynb`](file:///C:/Users/DELL/Downloads/Hackton/Task3/Task_3.ipynb)) containing all 5 required deliverables with visible outputs, inline charts, candidate pruning tables, empirical complexity analysis across 5 dataset sizes ($N$) and 5 support thresholds ($\text{min\_support}$), and the final timed cell.
   - Official CSV deliverables [`frequent_itemsets.csv`](file:///C:/Users/DELL/Downloads/Hackton/Task3/frequent_itemsets.csv) and [`rules.csv`](file:///C:/Users/DELL/Downloads/Hackton/Task3/rules.csv) (also saved in [`output/`](file:///C:/Users/DELL/Downloads/Hackton/Task3/output)).
3. **Full-Stack Market Basket Analytics Web Application**:
   - **Backend API** ([`backend/main.py`](file:///C:/Users/DELL/Downloads/Hackton/Task3/backend/main.py)): Asynchronous Starlette + Pydantic v2 + Uvicorn REST server.
   - **Relational Database** ([`backend/database.py`](file:///C:/Users/DELL/Downloads/Hackton/Task3/backend/database.py)): Indexed SQLite database (`data/arm_analytics.db`) storing all $23,874$ frequent itemsets and $236,401$ association rules across both `full` and `dev` datasets, plus empirical scaling benchmarks and live mining runs.
   - **Responsive Frontend Dashboard** ([`frontend/index.html`](file:///C:/Users/DELL/Downloads/Hackton/Task3/frontend/index.html), [`frontend/styles.css`](file:///C:/Users/DELL/Downloads/Hackton/Task3/frontend/styles.css), [`frontend/app.js`](file:///C:/Users/DELL/Downloads/Hackton/Task3/frontend/app.js)):
     - **Overview & Candidate Pruning**: KPI cards, candidate vs. frequent charts/tables by size $k$, basket length histogram, and top individual items.
     - **Frequent Itemsets Explorer**: Filter by size $k$, item ID, minimum count, sort, paginate, and export CSV.
     - **Association Rules Explorer**: Filter by antecedent $A$, consequent $C$, minimum confidence, minimum lift, cardinality $|A|, |C|$, sort, and export CSV.
     - **Smart Basket Recommender**: Interactive cart simulator that triggers real association rules $A \subseteq \text{Basket} \Rightarrow C$ and ranks cross-sell recommendations by confidence, lift, and support.
     - **Live Eclat Mining Studio & Complexity Benchmarks**: Execute custom mining jobs on preset slices or custom pasted transactions, persist runs to SQLite, and inspect empirical scaling charts.

---

## 2. Technology Stack

| Component | Technology | Version |
|---|---|---|
| **Language** | Python | 3.13.15 |
| **Core Mining Engine** | NumPy (`uint64` Vertical Bitsets + `np.bitwise_count`) | 2.5.4 |
| **Data Analysis & Notebooks** | Pandas, Pillow, Jupyter `.ipynb` | 3.1.1 / 13.0.0 |
| **Backend API** | Starlette + Uvicorn + Pydantic v2 | 1.10.0 / 0.54.0 / 2.14.2 |
| **Database** | SQLite 3 (WAL mode, composite indices) | Built-in (`sqlite3`) |
| **Frontend** | Modern HTML5 + CSS3 + ES6+ JavaScript + HTML5 Canvas | Baseline Widely Available |
| **Automated Testing** | Pytest | 9.2.0 |

---

## 3. Folder Structure

```text
C:\Users\DELL\Downloads\Hackton\Task3\
├── arm_task\                          # Input datasets & dev answer keys
│   ├── transactions.txt               # Full dataset (500,000 transactions)
│   ├── dev_transactions.txt           # Dev dataset (50,000 transactions)
│   ├── dev_frequent_itemsets.csv      # Dev answer key (12,141 frequent itemsets)
│   ├── dev_rules.csv                  # Dev answer key (125,999 association rules)
│   └── params.json                    # {"min_support": 0.003, "min_confidence": 0.6}
├── backend\
│   ├── __init__.py
│   ├── config.py                      # Environment variable & path configuration
│   ├── miner.py                       # Vertical-Bitset Eclat & Rule Generation Engine
│   ├── database.py                    # SQLite schema & analytical query layer
│   ├── schemas.py                     # Pydantic v2 validation models
│   ├── seed.py                        # Pipeline execution, benchmarking & DB seeding script
│   └── main.py                        # Starlette ASGI REST API & static file server
├── frontend\
│   ├── index.html                     # Responsive 5-tab Market Basket Analytics UI
│   ├── styles.css                     # Modern dark-slate UI styling
│   └── app.js                         # Frontend state, API integration & Canvas charts
├── notebooks\
│   └── generate_notebook.py           # Generates the executed Colab Jupyter notebooks
├── output\
│   ├── frequent_itemsets.csv          # Generated full-dataset frequent itemsets (11,733 rows)
│   ├── rules.csv                      # Generated full-dataset association rules (110,402 rows)
│   ├── dev_frequent_itemsets.csv      # Generated dev frequent itemsets (12,141 rows)
│   ├── dev_rules.csv                  # Generated dev association rules (125,999 rows)
│   └── benchmarks.json                # Empirical scaling & candidate pruning telemetry
├── data\
│   └── arm_analytics.db               # Populated SQLite database
├── tests\
│   ├── test_miner.py                  # Unit, edge-case & ground-truth accuracy tests
│   └── test_api.py                    # REST API, validation & E2E integration tests
├── docs\
│   ├── TASK3_REQUIREMENTS.md          # Complete Task 3 requirements specification
│   ├── PROJECT_ANALYSIS.md            # Inspection & gap analysis report
│   ├── IMPLEMENTATION_PLAN.md         # Architecture & algorithmic design document
│   ├── TESTING_REPORT.md              # Executed test results & benchmark report
│   ├── MANUAL_SETUP.md                # Step-by-step manual checklist for user
│   └── FINAL_DELIVERABLES.md          # Complete inventory of final deliverables
├── Task3_Association_Rule_Mining.ipynb # Primary executed Colab-ready deliverable notebook
├── Task_3.ipynb                       # Updated starter notebook with complete solution
├── frequent_itemsets.csv              # Root copy of full-dataset frequent itemsets deliverable
├── rules.csv                          # Root copy of full-dataset association rules deliverable
├── app.py                             # Application server entrypoint
├── .env.example                       # Environment configuration template
├── requirements.txt                   # Locked Python environment packages
└── README.md                          # Project documentation
```

---

## 4. Installation & Environment Setup

All commands run inside `C:\Users\DELL\Downloads\Hackton\Task3`:

```powershell
cd C:\Users\DELL\Downloads\Hackton\Task3

# 1. (Already created) If setting up a fresh virtual environment:
C:\Users\DELL\AppData\Local\Programs\Python\Python313\python.exe -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 2. (Optional) Copy .env.example to .env to customize host/port/paths:
Copy-Item .env.example .env
```

---

## 5. Database Setup & Re-Seeding

The SQLite database (`data/arm_analytics.db`) and output CSV deliverables (`frequent_itemsets.csv`, `rules.csv`) are already populated and verified. To re-run the complete mining pipeline, scaling benchmarks, and database seeding from scratch:

```powershell
cd C:\Users\DELL\Downloads\Hackton\Task3
.\.venv\Scripts\python.exe -m backend.seed
```

To regenerate the executed Jupyter Notebooks (`Task3_Association_Rule_Mining.ipynb` and `Task_3.ipynb`):

```powershell
.\.venv\Scripts\python.exe -m notebooks.generate_notebook
```

---

## 6. How to Run the Full-Stack Application (Backend + Frontend)

```powershell
cd C:\Users\DELL\Downloads\Hackton\Task3
.\.venv\Scripts\python.exe app.py
```

Then open your browser at:
- **Web Dashboard**: `http://127.0.0.1:8000`
- **Health Check API**: `http://127.0.0.1:8000/api/health`
- **Dataset Stats API**: `http://127.0.0.1:8000/api/stats`

---

## 7. How to Run Automated Tests

```powershell
cd C:\Users\DELL\Downloads\Hackton\Task3
.\.venv\Scripts\python.exe -m pytest -v
```

