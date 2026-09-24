# API contract

All endpoints are implemented in `api/main.py`. `GET /health` checks the database, job count, chunk count, and active-index presence. `GET /api/analytics/overview`, `/skills`, `/jobs`, `/filters`, and `/quality` provide validated, deterministic data. `/jobs` supports `limit` (1–100) and nonnegative `offset`. Other analytics endpoints accept optional role, country, city, seniority, company, workplace, and skill filters.

`POST /api/assistant/query` takes `{"question":"What percentage of jobs mention Python?","filters":{}}` and selects analytics or retrieval. `POST /api/rag/query` accepts descriptive questions only. Responses contain `route`, `answer`, `data`, `key_points`, `skills`, `sources`, `evidence`, and `metadata`. Unavailable data and rejected requests return clear HTTP errors.

`POST /api/rag/reindex` accepts optional `{"limit":100}` for a partial development index. HTTP indexing requires configured `ADMIN_TOKEN` and a matching `X-Admin-Token` header; otherwise it is disabled. The CLI `python -m src.rag.indexing` is available without HTTP access. This API is intended for local portfolio use and needs authentication/rate limits before public deployment.
