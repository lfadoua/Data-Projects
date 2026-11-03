# Data Job Market Intelligence: the story from an advert to an answer

This project turns 12,217 historical job advertisements into a searchable
application. It can count skills, explore locations and show passages that
support an answer about a role. The advertisements were collected on January
12–17, 2024. This is a study of that collection, not a monitor of today's vacancies.

## Chapter 1 — The problem

You open a job advertisement for a Data Engineer. It asks for Python, SQL and
cloud experience. The next advert mentions different tools. After reading ten,
it is already hard to remember which requirements appeared where.

Now imagine having more than twelve thousand advertisements. You might want to
know how often Python appears, which cities occur most, or what senior engineers
are expected to do. Reading every description again for each question would be
slow. Keeping an informal tally would make mistakes easy.

There are also two different kinds of question hiding here. "How many?" needs a
count. "What responsibilities?" needs the wording of real advertisements. The
application had to handle both without confusing an example with a statistic.

## Chapter 2 — The idea

Data Job Market Intelligence puts the collection behind one interface. A visitor
can start with a chart, narrow the results to a country or role, open an advert,
then ask a question about the selected jobs.

For a numerical question, the application checks the database. For a descriptive
question, it finds relevant passages and shows their sources. When the selected
passages do not support an answer, it says so.

That connection between an answer and its origin is the central design choice.
A useful response should give the reader something they can inspect.

## Chapter 3 — The data

The starting material was three existing CSV files. A CSV is a plain table saved
as text, with one row after another. `job_postings.csv` contains advert details,
`job_summary.csv` supplies description text, and `job_skills.csv` supplies source
skill information. The original project report identifies the source collection
as Kaggle's [Data Science Job Postings & Skills (2024)](https://www.kaggle.com/datasets/asaniczka/data-science-job-postings-and-skills). The local imported
collection contains 12,217 postings; it should not be confused with a claim about
the size of the entire source dataset.

The code keeps original and normalized titles, company, location, country, city,
seniority, workplace type, employment type, description, detected skills and the
original posting link. Salary and publication fields exist in the schema, but
their presence in the schema does not mean the imported data contains them.
Missing information is kept missing.

The dates January 12–17, 2024 describe collection coverage. They are not reliable
publication dates for every advert. The source is geographically uneven and
includes titles outside the main data-role categories. Some original links may
no longer accept applications. These limits matter when interpreting a chart.

Raw CSVs, processed rows, model caches and database credentials are excluded from
Git. Their redistribution rights have not been established by this readiness
review. A clone of the repository therefore contains the software and controlled
tests, not a public copy of the private working database.

## Chapter 4 — From raw data to structured information

The first task was to make the three tables agree about which advert a row
described. The ingestion code recognizes alternative column names and joins
related rows through their posting link. It checks that an auxiliary table does
not offer ambiguous duplicate join keys.

Descriptions then pass through conservative cleaning: HTML markup and script or
style fragments are removed, encoded characters are decoded, and spacing is
tidied. The underlying responsibilities are not rewritten. Stable identifiers
let later records point back to the same job.

Normalization gives common variants a shared label. A title matching a defined
Data Engineer rule can be grouped with other matching titles. An unmatched title
stays "Other / Unclassified". A missing city does not become an invented city.
The code also avoids treating a crawler's search location as a verified job
location.

Skill extraction uses a configurable vocabulary and aliases. For an illustrative
sentence such as "Build pipelines with Python and SQL", the application can
record Python and SQL against that job. That example explains the rule; it is
not an extra observation added to the real dataset.

The resulting records are stored in PostgreSQL, an organized database that keeps
jobs, skills and text passages connected. Each job can have several skills, and
each skill is counted at most once for that job. The implementation is in
`src/preprocessing/` and `src/database/`. No ingestion or database rewrite was
performed during this documentation mission.

## Chapter 5 — How SQL answers numerical questions

Consider a real question from the project:

> What percentage of jobs mention Python?

The recorded answer is **5,121 of 12,217 postings, or 41.92%**. "Mention" means
the configured extraction rules detected Python in the combined job text and
source skill information. It does not mean all those employers require the same
level of Python knowledge.

SQL is the language used to ask organized databases for results. Here, it counts
the matching jobs, counts those with the Python skill, then divides the second
number by the first and multiplies by 100. The percentage can be checked with an
independent database query, which was done in the recorded validation.

A job with Python listed several times still counts once. With filters applied,
the denominator becomes the matching group. The application uses predefined
query logic rather than asking a language model to invent and execute SQL.
That makes numerical answers easier to reproduce and inspect.

## Chapter 6 — How RAG finds useful passages

Think of a librarian who receives a question, finds a few relevant pages and
marks the lines used in the answer. Retrieval-Augmented Generation, shortened to
RAG, follows that broad pattern. In this application, retrieval can also support
an answer without asking a language model to write anything.

Long job descriptions are divided into smaller passages called **chunks**.
Splitting follows sentences and paragraphs where possible, with some overlap so
nearby context can survive a boundary. The code measures its chunk budget in
words. A job can produce several passages.

Each passage receives an **embedding**: a list of numbers that helps compare its
meaning with another piece of text. Imagine a library map where related topics
tend to be placed near each other. The actual map has 384 numerical dimensions,
not physical shelves. The V2 index contains **30,955 passages and embeddings**,
using the pretrained **BAAI/bge-small-en-v1.5** model through FastEmbed. The
project did not train this model from scratch.

PostgreSQL stores those vectors with **pgvector**, an extension for comparing
such number lists. A question gets its own vector, and vector search retrieves
candidate passages with similar representations. Metadata filters can restrict
the jobs considered.

The candidates are then **reranked**, meaning their order is checked again with
the question in mind. The code supports a small MiniLM cross-encoder, which
scores question/passage pairs, and a hybrid method combining text and vector
signals. The recorded laptop profile uses the hybrid method. The application
selects distinct jobs so one long advert does not occupy every evidence slot.

The selected passages receive source IDs such as S1 and S2. Those IDs belong to
that response and link to real job records. The answer can quote complete source
sentences, or use tightly constrained optional wording checked against them.

The librarian analogy has a limit: finding a page does not prove everything on
it is true. A matching quote establishes where the words came from. It does not
prove every possible interpretation. If the selected passages are inadequate,
the application returns an explicit insufficient-evidence answer.

## Chapter 7 — The AI Assistant

The assistant has three practical paths:

| Path | What happens | When it is useful |
|---|---|---|
| SQL Analytics | The database calculates a count, percentage or distribution. | Numerical questions. |
| Extractive fast | Relevant complete sentences are selected and cited, without a generative model. | Inspecting what the selected adverts actually say. |
| Optional Qwen/Ollama | A local model proposes wording, then the application checks and filters it. | Trying bounded wording based on selected evidence. |

**Extractive fast is the initial choice for new UI sessions and the recommended
mode on this laptop.** Ollama is a program that runs a language model on the
computer. Qwen 2.5 1.5B is the small model tested for optional generation. No paid
model API or account is needed for that local path.

Using a model for every question would add CPU time without improving a simple
count. It would also create more opportunities for unsupported statements.
The numerical route therefore stays separate.

During the October 30 generation check, four measured attempts returned accepted
bounded responses. Two of those responses lost one proposed claim during
validation. Across the six accepted claims, four used attribution to a posting
and two remained verbatim. This is a small demonstration of controlled wording,
not evidence that arbitrary paraphrases are reliable.

Unknown sources, invented quotations, invalid or truncated output and unsupported
claims are rejected. A failed generation can fall back to clearly labelled
extraction. A response with no adequate evidence abstains. Neither fallback nor
abstention is counted as an accepted generated answer.

## Chapter 8 — Building the application

The pieces have separate jobs, which makes it easier to test a failure in one
without guessing about all the others.

| Piece | Plain-language role | Implementation |
|---|---|---|
| Python | The language connecting data preparation, calculations and application logic. | `src/`, `api/`, `app/`. |
| PostgreSQL / Supabase | The organized store; Supabase hosts the existing PostgreSQL instance. | Linked job, skill, chunk and index-state tables. |
| SQL Analytics | The counting and grouping rules. | `src/analytics/`. |
| RAG | The search-and-evidence path for descriptive questions. | `src/rag/`. |
| FastAPI | The service desk that accepts requests and returns structured answers. | `api/main.py`. |
| Streamlit | The screen a visitor uses to explore charts, jobs and answers. | `app/Home.py` and the page modules. |
| Ollama / Qwen | The optional local writing component. | `src/llm/` and the generation prompts. |

The screen calls FastAPI. It does not run its own competing version of the
business rules. Responses include the chosen route, filters, evidence and source
information, so the interface can explain what happened.

## Chapter 9 — Docker: making the application reproducible

Software that runs on one laptop can fail on another because installed packages
or start commands differ. Docker helps package those choices.

A **Dockerfile** is a build recipe. An **image** is the built package produced
from that recipe. A **container** is a running instance of an image. **Docker
Compose** describes how several containers connect and start together.

The owner manually built the API and frontend images on Windows 11 using Docker
Desktop, WSL2 and Ubuntu. The working configuration is `compose.supabase.yml`:

| Component | Inside the Compose network | Windows access |
|---|---|---|
| FastAPI | `api:8000` | `http://localhost:8002` |
| Streamlit | Port 8501, calling `http://api:8000` | `http://localhost:8502` |
| PostgreSQL | Existing external Supabase instance | Credentials loaded locally, never published. |

This setup has no new database or setup service. The original `docker-compose.yml`
remains a separate configuration with local database/setup services; it is not
the quick start for the existing Supabase corpus.

The different Windows ports also allow the container setup to avoid the native
application's usual 8000/8501 ports. A port is simply the numbered doorway through
which a program receives requests.

The owner's reported checks include two healthy containers, the real database
counts, the Python percentage and an extractive answer with two sources. The
readiness review independently checked Compose configuration successfully, but
could not reach the Docker engine or mapped ports in its execution session.
These are different evidence sources, both labelled in the validation summary.
The application has been tested locally; it is not publicly deployed.

## Chapter 10 — How we tested the work

How can someone trust the result beyond a screenshot? Each layer needs a
different kind of check.

**Unit tests** use small controlled examples to check one rule, such as skill
counting or rejection of a false citation. **Integration tests** check parts
working together. Three opt-in tests read the real PostgreSQL database to verify
vectors, links, counts and response sources. The ordinary CI test selection does
not need access to that private database.

API checks exercise the service's real requests. SQL answers have been compared
with independent counts. RAG checks follow source IDs back to actual job/chunk
records and verify quotation text. Generation tests deliberately include missing
sources, wrong quotations, unsupported additions, truncated output and refusal.
Streamlit has also been operated in a browser to check filters, cards, route
labels and evidence displays.

The October 30 record contains **193 passing tests, including three PostgreSQL
tests**. That result was checked against its saved output, not inferred from a
README sentence. The [validation summary](PROJECT_VALIDATION_SUMMARY.md) records
the additional execution performed for this documentation/UI update separately.

**Ruff** checks code consistency and formatting. **GitHub Actions** contains the
automated workflow that can run checks on a push or pull request. A workflow file
does not prove that a hosted run passed; no such hosted success is claimed.

A passing unit test answers a limited question about controlled inputs. A real
environment test checks actual connections and processes. A **benchmark** measures
behaviour or time under stated conditions. An unverified result stays explicitly
unverified. For Docker runtime, the evidence is the owner's manual test report;
it is not relabelled as an agent-executed container run.

## Chapter 11 — Real results

| Result | Evidence and meaning |
|---|---|
| 12,217 jobs | Recorded PostgreSQL counts, also reported in the owner's Docker health check. |
| 30,955 V2 chunks and embeddings | Recorded complete index; BGE model, 384 dimensions. |
| Python: 5,121 / 12,217 = 41.92% | Reconciled SQL result, also manually checked through Docker. |
| Senior Data Engineer: two cited sources | Owner's Docker extractive test showed S1/S2 and about 1.9 seconds displayed time; not a latency guarantee. |
| 193 passing tests on October 30 | Saved full-suite execution, including three PostgreSQL tests; fresh checks have their own date in the summary. |
| API and frontend containers healthy | Owner-reported manual runtime evidence using existing external Supabase. |
| Screen → API → database → answer | Recorded native checks and separately reported Docker checks. |

The [validation summary](PROJECT_VALIDATION_SUMMARY.md) is the compact evidence
ledger, with dates, scope and remaining gaps. No result here claims that this
historical sample represents the current worldwide job market.

## Chapter 12 — Challenges, lessons and limits

Separating a percentage from a descriptive question turned out to be an
architectural decision. Counts need the whole matching group. A descriptive
answer may use only two adverts. Presenting those two adverts as a market-wide
pattern would make the answer misleading even if every quotation were genuine.

Generation introduced a different problem. Qwen sometimes added a general
statement about all Data Engineers or changed a sentence beyond what the
validator could justify. The correction narrowed the wording task. A specific
formatting tolerance allows a final full stop on an otherwise unpunctuated
source line; it does not allow new responsibilities or altered actors.

The laptop has about 8 GB of RAM and uses CPU generation. Model reuse and short
contexts help, but optional generation still takes seconds longer than extraction.
The October 30 benchmark's Senior/AWS service medians were about 11.55/16.53
seconds. Qwen 3B was not rerun in that comparison because available RAM was below
the chosen threshold. No larger model was downloaded for this readiness review.

Keeping the working Supabase database also required care. The external Compose
file avoids a second database and a setup step that could load or index data.
Port choices and the frontend's internal API address are documented explicitly.

The project currently has a bounded English question router, conservative
evidence selection and optional restricted generation. It lacks a general
semantic proof for arbitrary paraphrases, a representative current-market feed
and a verified public deployment. Two tested questions abstained because the
selected context was inadequate. The original V1 index is retained, including
its recorded two zero-vector limitation; V2 is the active retrieval path.

There is also a security action outside the code: a previously exposed database
credential still needs manual rotation. A clean file scan does not undo an old
exposure. That action must be completed before public publication.

## Chapter 13 — What the work teaches, and what comes next

The project connects data engineering to something a person can use. Preparing
rows is only part of the job: the counts must remain consistent, the service must
answer requests, and the screen must show the limits of an answer as well as its
content.

It demonstrates applied SQL and Python, database modelling, data-quality checks,
pretrained semantic retrieval, API and UI development, testing and container
configuration. The data science work concerns representations, retrieval,
evaluation and interpretation; it is not a claim of training a new language model.

The next steps are specific: rotate the exposed credential, confirm the hosted
GitHub workflow after an authorized publication, and expand human-reviewed
retrieval/answer examples before loosening any generation rules. A future live
data feed would need its own collection process, source permissions and validation.

The portfolio result is a working route from a job advert to a count or a cited
answer, with enough evidence for another reader to check what the system did.
