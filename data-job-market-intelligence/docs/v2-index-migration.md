# V2 index migration and rollback

Run these commands from the application directory with its existing `.env`. Keep the
database password in `.env`; do not put it in a command or commit it.

## Before migration

Check that the source load is complete and the V1 index is healthy:

```powershell
.\.venv\Scripts\python.exe -m src.database.init_db
Invoke-RestMethod http://127.0.0.1:8000/health
```

The full source load contains 12,217 jobs. V1 is stored in `djmi.job_chunks`
with 128-dimensional vectors and state row 1. V2 is stored separately in
`djmi.job_chunks_v2` with 384-dimensional vectors and state row 2. No table
rename, vector-dimension alteration, or delete of V1 is part of this migration.

## Build and verify V2

```powershell
.\.venv\Scripts\python.exe -m src.rag.indexing --v2
Invoke-RestMethod http://127.0.0.1:8000/health
.\.venv\Scripts\python.exe evaluation/review_v2.py
```

The index command embeds all descriptions before opening the replacement
transaction. It then replaces only the V2 chunks and state row 2 in one
transaction. A failed model call or transaction leaves the previous active
index available. The full run is CPU-intensive and can take hours on a laptop.
Each completed embedding batch is saved under `data/models/v2-checkpoints/`.
If the computer stops, run the same command again: batches matching the exact
model, chunk content, and batch size are reused. A changed source or chunking
configuration gets a different checkpoint directory. These local files are
excluded from Git.
Do not use `--limit` for the final build: it intentionally activates a partial
development index. The health response should report 12,217 jobs, the V2 chunk
count, and `index_ready: true`. In a descriptive answer, check
`metadata.index.version == "v2"`, source IDs, and source URLs. Run the ten-question
review and inspect its recorded answers; route and link checks do not replace
human judgment of paraphrases.

## Roll back to V1

If V2 quality or performance is unacceptable, delete only state row 2 in a
transaction. The preserved V1 chunks and state row 1 then become active on the
next request. Use the app's configured SQLAlchemy engine so its schema setting
is honored:

```powershell
@'
from sqlalchemy import delete
from src.database.connection import get_engine
from src.database.models import IndexState
with get_engine().begin() as connection:
    connection.execute(delete(IndexState).where(IndexState.id == 2))
print("V1 retrieval is active again; V2 chunks remain for inspection.")
'@ | .\.venv\Scripts\python.exe -
```

Verify `/health` and a descriptive answer again. The rollback retains V2 chunk
rows so they can be inspected or rebuilt. Re-running the full `--v2` command
recreates state row 2 and activates V2. Reloading source jobs invalidates both
retrieval indexes; rebuild V2 after a source reload.
