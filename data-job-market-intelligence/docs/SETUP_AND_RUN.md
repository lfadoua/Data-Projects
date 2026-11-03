# Setup and run

This guide starts the existing application without changing the working database.
Python 3.11 is the CI version. The Git root is the **parent** of the application:

```text
repository/
  README.md
  .github/workflows/ci.yml
  data-job-market-intelligence/
    README.md
    compose.supabase.yml
    api/
    app/
    src/
    tests/
```

## What a clone includes

The repository contains code, controlled tests and curated validation evidence.
It excludes `.env`, CSV data, processed rows, database contents, model caches and
raw evaluation logs. To use the full dashboard, supply access to an **already
populated PostgreSQL/Supabase database with a complete V2 index**. The recorded
12,217-row database is not a public service or a bundled download.

Without that database, the offline tests still exercise controlled examples.
No default demo database or live-data collection is implied. Provisioning a new
corpus is a separate, intentional operation documented by the preprocessing and
indexing modules; it is not part of this safe start procedure. Review source
permissions before obtaining or redistributing the CSV files.

## Native Windows start

From the repository root:

```powershell
Set-Location .\data-job-market-intelligence
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Create `.env` from the example **only if it does not already exist**:

```powershell
if (-not (Test-Path -LiteralPath .env)) { Copy-Item .env.example .env }
notepad .env
```

Set your own existing database connection privately. Environment variables take
priority over `.env`. A nonempty `DATABASE_URL` takes priority over the `DB_*`
connection fields. Keep the host, port, user and SSL settings appropriate to your
database; Supabase connections normally use SSL. Do not publish the resulting file.

For an extractive-only installation, keep `LLM_PROVIDER=extractive`. No model API
key is needed for counts or extraction. V2 retrieval uses the embedding model
recorded in the database; its local weights may need downloading on the first
semantic query. That is distinct from rebuilding the corpus embeddings.

Start the API:

```powershell
.\.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

In a second terminal, from the **same application directory**:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app/Home.py --server.address 127.0.0.1 --server.port 8501
```

Open [Streamlit](http://127.0.0.1:8501), [health](http://127.0.0.1:8000/health)
or [API documentation](http://127.0.0.1:8000/docs). Stop these terminal processes
with `Ctrl+C`. No bootstrap, data loading, migrations or reindexing are needed
for the existing indexed database.

## Docker with existing external Supabase

Use the owner's `compose.supabase.yml` from the application directory. It contains
only API and frontend services. `.env` supplies the API's existing database
configuration and is not copied into an image. The API has a local `data/` mount
for caches; keep that directory local.

From Windows PowerShell, or from the application directory in your working
Ubuntu/WSL terminal with Docker available:

```text
docker compose -f compose.supabase.yml config --quiet
docker compose -f compose.supabase.yml build api
docker compose -f compose.supabase.yml build frontend
docker compose -f compose.supabase.yml up -d --no-deps api
docker compose -f compose.supabase.yml up -d --no-deps frontend
docker compose -f compose.supabase.yml ps
```

These are the commands the owner reported using successfully. This review did
not rebuild or start containers. API/Streamlit publish only to loopback:

- API: [localhost:8002/health](http://localhost:8002/health).
- UI: [localhost:8502](http://localhost:8502).
- Frontend-to-API traffic stays inside Compose at `http://api:8000`.

The original `docker-compose.yml` is a separate local-database/setup workflow.
Do not substitute it for the external-Supabase commands: it can initialize/load
and index its own database. Do not use volume-deleting commands on working data.

Select **Extractive fast** for the recorded Docker SQL/RAG examples. Running a
host Ollama instance from a container is a different network configuration and
has not been validated here. Local Docker tests are not a public deployment.

If this shell cannot reach the Docker engine, use the terminal where your Docker
Desktop/WSL setup works. A missing engine in one session does not disprove the
owner's earlier runtime checks. Do not reconfigure the database to solve that
engine-access problem.

## Tests and evaluations

From the application directory, the following wrapper runs Pytest and Ruff,
masking configured secrets before it saves or displays diagnostics:

```powershell
.\.venv\Scripts\python.exe -m evaluation.safe_checks --output evaluation/results/offline-checks.json
```

CI's equivalent test selection is `python -m pytest -q -m "not live" --tb=short`.
Offline tests use isolated temporary fixtures and mock generation; they do not
use the working Supabase database. To deliberately include the three read-only
PostgreSQL tests, choose this instead:

```powershell
.\.venv\Scripts\python.exe -m evaluation.safe_checks --live --output evaluation/results/live-checks.json
```

Do not run both just to duplicate validation. Real Qwen benchmarks are separate
from these tests and can be slow on CPU. See the [RAG guide](rag-local-optimization.md)
and [validation summary](PROJECT_VALIDATION_SUMMARY.md). The source is fixed to
historical January 2024 data until someone intentionally supplies a new corpus.
