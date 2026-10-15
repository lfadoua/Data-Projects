# API contract

All endpoints are implemented in `api/main.py`. `GET /health` checks the database, job count, chunk count, and active-index presence. `GET /api/analytics/overview`, `/skills`, `/jobs`, `/filters`, and `/quality` provide validated, deterministic data. `/jobs` supports `limit` (1–100), nonnegative `offset`, and optional `search` (at most 200 characters). Search matches literal text in job title, company, or cleaned description, using bound parameters and escaped SQL wildcard characters. Analytics endpoints accept optional role, country, city, seniority, company, workplace, and skill filters.

`GET /api/system/status` reports the preferred active index version, stored chunk/embedding counts, dimensions, readiness, partial-index flag, activation timestamp, and database engine label. It is read-only and does not return connection credentials. The dashboard uses it separately from the dated validation artifact.

`POST /api/assistant/query` takes `{"question":"What percentage of jobs mention Python?","filters":{}}` and selects analytics or retrieval. `POST /api/rag/query` accepts descriptive questions only. Responses contain `route`, `answer`, `data`, `key_points`, `skills`, `sources`, `evidence`, and `metadata`. Unavailable data and rejected requests return clear HTTP errors.

`POST /api/rag/reindex` accepts optional `{"limit":100}` for a partial development index. HTTP indexing requires configured `ADMIN_TOKEN` and a matching `X-Admin-Token` header; otherwise it is disabled. The CLI `python -m src.rag.indexing` is available without HTTP access. This API is intended for local portfolio use and needs authentication/rate limits before public deployment.
