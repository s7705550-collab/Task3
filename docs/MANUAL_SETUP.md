# Phase 9: Manual Work Required From You (`MANUAL_SETUP.md`)

Everything that could be implemented, mined, verified, seeded into SQLite, and tested automatically has already been completed in `C:\Users\DELL\Downloads\Hackton\Task3`.

Crucially, **Task 3 does NOT require any external paid API keys, cloud database credentials, or third-party authentication accounts** because `RC3_AI_Hackathon.docx` specifies that Task 3 runs purely on raw local/Colab files using standard Python + NumPy/Pandas/Matplotlib.

Below is the exact checklist of manual actions required from you for **viewing the live web app in your browser** and **submitting your final Task 3 hackathon deliverables**.

---

## Checklist of Manual Tasks

### Manual Task 1: Start the Server to View the Web Dashboard in Your Browser (Optional Local Exploration)

1. **What you need to do**: Launch `app.py` in your local PowerShell terminal if you want to interact with the web dashboard in Chrome/Edge.
2. **Why it is necessary**: Automated tests and sandboxed server checks stop after verification so no background processes are left hanging on your machine.
3. **Where you need to do it**: PowerShell terminal in `C:\Users\DELL\Downloads\Hackton\Task3`.
4. **Exact step-by-step instructions**:
   ```powershell
   cd C:\Users\DELL\Downloads\Hackton\Task3
   .\.venv\Scripts\python.exe app.py
   ```
   Then open **`http://127.0.0.1:8000`** in your browser.
5. **Information or credentials needed**: None (no API keys or login required).
6. **How to verify it is completed**: The top-right status pill on `http://127.0.0.1:8000` will show green **`SQLite Ready (236,401 rules)`**, and you can browse all 5 tabs (Overview, Frequent Itemsets, Association Rules, Smart Basket Recommender, and Live Miner).

---

### Manual Task 2: Run "Restart Session and Run All" on Google Colab Before Final Submission

1. **What you need to do**: Upload `Task3_Association_Rule_Mining.ipynb` (and `arm_task/student_data.zip` or mount your Google Drive containing `RC3 AI Hackathon/arm_task`) to Google Colab and run `Runtime -> Restart session and run all` on a **free CPU runtime**.
2. **Why it is necessary**: The hackathon rules in `RC3_AI_Hackathon.docx` (Page 1, *Technical rules for Tasks 2 and 3*) state:
   - *"Google Colab, free CPU runtime only. Choose Runtime -> Change runtime type -> CPU. No GPU, TPU or high-RAM option."*
   - *"Run Runtime -> Restart session and run all before you submit."*
3. **Where you need to do it**: [https://colab.research.google.com/](https://colab.research.google.com/)
4. **Exact step-by-step instructions**:
   1. Open [Google Colab](https://colab.research.google.com/) and upload `C:\Users\DELL\Downloads\Hackton\Task3\Task3_Association_Rule_Mining.ipynb`.
   2. Click **Runtime -> Change runtime type** and confirm **CPU** is selected (with High-RAM turned off).
   3. Upload `C:\Users\DELL\Downloads\Hackton\Task3\arm_task\student_data.zip` to `/content/` in the Colab file sidebar (or mount Google Drive where `RC3 AI Hackathon/arm_task` is stored — Stage 1 of the notebook automatically detects both!).
   4. Click **Runtime -> Restart session and run all**.
   5. Wait ~15 seconds for all 6 code cells to finish executing.
   6. Download the executed `.ipynb` (`File -> Download -> Download .ipynb`) and the generated `frequent_itemsets.csv` and `rules.csv` (or use the exact copies already generated in `C:\Users\DELL\Downloads\Hackton\Task3\`).
5. **Information or credentials needed**: Your Google account to access Google Colab.
6. **How to verify it is completed**:
   - Every cell in the notebook shows execution numbers `[1]` through `[6]` with visible outputs and charts.
   - Cell `[3]` prints `Missing: 0 | Extra: 0 | Wrong Count: 0` for both Dev Frequent Itemsets (`12,141`) and Dev Association Rules (`125,999`).
   - Cell `[6]` (the final timer cell) prints `Frequent Itemsets Found : 11,733 -> saved to frequent_itemsets.csv` and `Association Rules Found : 110,402 -> saved to rules.csv` with the recorded Colab CPU runtime.

---

### Manual Task 3: Final Hackathon Submission

1. **What you need to do**: Submit the required Task 3 deliverables to the hackathon submission portal before the deadline.
2. **Why it is necessary**: Only submitted deliverables can be graded by the hackathon evaluators.
3. **Where you need to do it**: Your organizer's official submission portal / LMS.
4. **Exact files to submit for Task 3**:
   - `C:\Users\DELL\Downloads\Hackton\Task3\Task3_Association_Rule_Mining.ipynb` (Notebook with all outputs visible)
   - `C:\Users\DELL\Downloads\Hackton\Task3\frequent_itemsets.csv` ($11,733$ itemsets + header = $11,734$ lines)
   - `C:\Users\DELL\Downloads\Hackton\Task3\rules.csv` ($110,402$ rules + header = $110,403$ lines)
   - (Optional/Bonus) Full project folder `C:\Users\DELL\Downloads\Hackton\Task3` containing the interactive web dashboard, REST API, SQLite database, and test suite.
5. **Information or credentials needed**: Your hackathon student/participant credentials.
6. **How to verify it is completed**: Confirm on the submission portal that `Task3_Association_Rule_Mining.ipynb`, `frequent_itemsets.csv`, and `rules.csv` are uploaded and non-empty.

