# Evaluation

`questions.json` contains 26 reviewed route/metadata prompts, including no-evidence and ambiguous cases. Run `python -m src.evaluation.evaluator --versions v1 v2` against a loaded database and index. Results are measured JSON files in `results/`. Recall@K needs job-ID relevance labels; quote validity is a traceability proxy rather than a semantic correctness judgment.
