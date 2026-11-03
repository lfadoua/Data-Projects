# Validation summary

Evidence reviewed on **31 October 2026**. Dates and provenance are part of each
claim. The application studies postings collected January 12–17, 2024.

## Current results

| Result | Date and source | Scope |
|---|---|---|
| **196 tests passed**, including **3 PostgreSQL tests**, 50.49 s, two deprecation warnings | Fresh agent execution, 31 October | `evaluation.safe_checks --live`; controlled tests plus read-only checks on the configured PostgreSQL instance. |
| Ruff check and format passed; 120 files formatted | Fresh agent execution, 31 October | Existing application and new UI-provenance tests. |
| **193 tests passed**, including 3 PostgreSQL tests, 32.53 s | Saved execution, 30 October | Previous full-suite result, independently checked in its saved artifact; not mislabelled as today's run. |
| 12,217 jobs; 23,638 V1 chunks; 30,955 V2 chunks and embeddings, 384 dimensions | Recorded database audits; read-only integration checked again 31 October | V2 BAAI/bge-small-en-v1.5, FastEmbed/pgvector; no loading, corpus embedding rebuild or migration in this review. |
| Python detected in 5,121 of 12,217 jobs: **41.92%** | Independent SQL reconciliation recorded 30 October; owner's Docker example reported 31 October | Whole imported corpus, before additional filters; one count per job/skill. |
| Six API routes and native Streamlit behaviour checked | Recorded local validation, 30 October | New test run covers API/UI contracts and real DB integration; the entire browser campaign was not repeated. |
| Four accepted Qwen 1.5B responses / four generation attempts, zero fallback | Real serial benchmark, 30 October | Two questions × two repeats, warmup excluded. Two responses each dropped one claim. Four other cases abstained without calling Ollama. |
| Two images built; two containers healthy; Home, SQL and two-source extractive RAG working | **Owner-reported manual runtime evidence**, supplied 31 October | Docker Desktop + WSL2 + Ubuntu, `compose.supabase.yml`, existing external Supabase, Windows ports 8002/8502. |
| External-Supabase Compose configuration valid | Fresh agent check, 31 October, exit 0 | `docker compose -f compose.supabase.yml config --quiet`; no build/start performed by the agent. |
| Docker engine and mapped endpoints unavailable to this session | Fresh agent probe, 31 October | Docker CLI exists; engine pipe unavailable, ports 8002/8502 refused connections. This does not negate the owner's earlier successful run. |
| Hosted GitHub Actions | **Unverified** | Local workflow inspected, not dispatched or observed running on GitHub. No deployment claimed. |

Portable summaries are included as
[30 October evidence](evidence/validation-2026-10-30.json) and
[31 October evidence](evidence/validation-2026-10-31.json).
Raw logs and benchmark outputs remain ignored local artifacts. These curated
records are summaries of measurements, not a hosted CI badge or an independently
signed audit. Commands to reproduce applicable checks are in [Setup](SETUP_AND_RUN.md).

## What the tests prove

Tests exercise preprocessing rules on temporary fixtures, SQL counts, routing,
retrieval filters, accepted/rejected quotations, fallback, abstention and response
shapes. Three opt-in tests use the configured PostgreSQL database in read-only
paths. The other **193 tests** in the current suite can be selected without those
external integration tests. That number differs from the historical *193 total*
on October 30: three UI-provenance tests were added on October 31.

The two warnings come from the installed Starlette TestClient's HTTPX transition
and its deprecated AnyIO alias. They remain visible; no dependency upgrade or
warning suppression is presented as a correction.

## Generative limitations

The four accepted attempts are a small sample of restricted wording. Across six
accepted claims, four use posting attribution and two remain literal source
sentences. The model is not validated for arbitrary paraphrases or translation.
Senior/AWS service medians were **11.553 s / 16.535 s** in that CPU benchmark;
they are not browser-time guarantees. No generative benchmark was repeated for
this documentation mission.

Each returned claim/source is checked against actual retrieved PostgreSQL text.
That establishes traceability, not general semantic entailment or the truth of
the underlying advertisement. `semantic_entailment_verified` remains false.
Fallback and insufficient-evidence responses never count as successful generated
answers. Extractive fast remains the recommended initial mode.

## Docker evidence, exactly

The owner reported building `data-job-market-intelligence-api` and
`data-job-market-intelligence-frontend`, then starting the two services with
`compose.supabase.yml`. Reported health: connected database, 12,217 jobs, 30,955
chunks, ready index. Reported examples: Python 41.92%; Senior Data Engineer
extractive answer, S1/S2, about **1.9 seconds displayed**.

The agent verified the configuration file and successful `config --quiet` only.
The engine was not accessible for an independent `ps` confirmation. No images or
containers were rebuilt, started or stopped. The original Compose workflow with
`db`/`setup` remains separate. Optional generation inside Docker and public hosting
have not been validated. See [Setup](SETUP_AND_RUN.md) for the correct ports and
working directory.

## Historical indicators are preserved

`app/assets/validation_snapshot.json` remains the **11 October** record: 61 tests
and 19/20 original Definition-of-Done criteria. Its Docker assessment describes
that date. It has not been rewritten into a fictitious 20/20 score.

`app/assets/current_validation.json` holds recent recorded test information and
the owner's Docker evidence with explicit provenance. Home displays recent
recorded tests and a user-verified Docker label. Validation still exposes the
original criteria table as historical. Opening either page does not run tests or
certify that containers are healthy now.

## Before publication

- Rotate the previously exposed PostgreSQL credential manually, update the local
  secret, and restart the clients. Follow the [rotation procedure](rotation-secrets.md).
- Check the hosted workflow when publication is authorized; a local YAML file
  does not prove it passed.
- Keep raw data, processed records, model caches, `.env` and raw diagnostics out
  of the repository. Source redistribution rights remain unverified here.

The [GitHub readiness report](github-readiness-report.md) records the publication
verdict and exact next steps. The older detailed reports remain dated records;
their local-artifact links are meant for this working copy, not evidence that
those raw artifacts are published on GitHub.
