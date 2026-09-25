# Evaluation

`questions.json` contains 26 reviewed route/metadata prompts, including no-evidence and ambiguous cases. Run `python -m src.evaluation.evaluator --versions v1 v2` against a loaded database and index. Results are measured JSON files in `results/`. Recall@K needs job-ID relevance labels; quote validity is a traceability proxy rather than a semantic correctness judgment.

For the final V2 release check, start FastAPI and run these commands from the application directory after the complete V2 index is active:

```powershell
.\.venv\Scripts\python.exe -m evaluation.check_index --version v2 --output evaluation/results/final-v2-index-audit.json
.\.venv\Scripts\python.exe -m evaluation.verify_v2_storage --output evaluation/results/final-v2-storage-verification.json
.\.venv\Scripts\python.exe -m evaluation.final_validation --expected-index v2 --output evaluation/results/final-v2-validation.json
.\.venv\Scripts\python.exe -m evaluation.compare_indexes --v1 evaluation/results/final-v1-baseline.json --v2 evaluation/results/final-v2-validation.json --output evaluation/results/final-v1-v2-comparison.json
$env:RUN_DB_INTEGRATION = "1"
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
```

The index audit counts PostgreSQL rows, checks pgvector dimensions, norms, source linkage, and the cosine index. The storage check compares every published pgvector embedding with its saved computed batch. The ten-question check independently reconciles quantitative answers with SQL and verifies every cited RAG source and quote against PostgreSQL. The comparison reports observed document overlap and latency; it does not infer a relevance score without labeled judgments. The JSON results are local validation artifacts excluded from Git.
