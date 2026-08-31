# Proactive Reporting Agent

A multi-agent AI system that collects data from a database, analyses trends and anomalies,
writes an executive report with an LLM, scores it with an evaluator loop, and proactively
delivers it by email or WhatsApp — on a schedule or on demand.

Ships with a FastAPI backend, a React dashboard, JWT auth with multi-tenant company
isolation, and scripts for the agent-pattern experiments the project was built to run.

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

---

## Features

- **9-agent LangGraph pipeline** — collection → quality gate → analysis → RAG → writing → evaluation loop → delivery → feedback
- **Statistical analysis** — trend detection (Mann-Kendall), anomaly detection (Isolation Forest, z-score), forecasting (Prophet), category and sector comparison
- **RAG over past reports** — ChromaDB retrieval with temporal filtering, so a report never cites the future
- **Evaluator-optimizer loop** — the report is scored and rewritten up to `MAX_EVALUATOR_ITERATIONS` times before it ships
- **Delivery** — SMTP email with an HTML template, optional WhatsApp via Twilio
- **Bring your own API key** — each user enters their own OpenAI key and model in the dashboard; it stays in their browser and is never stored server-side
- **Multi-tenant API** — JWT auth, per-company data isolation, admin endpoints for companies, users, and data upload
- **React dashboard** — pipeline progress, KPI cards, charts, report viewer, admin panel
- **Scheduler** — APScheduler monthly job, disabled by default
- **Experiment scripts** — A/B test of prompting strategies and a prompt-chaining vs. multi-agent pattern comparison

---

## Architecture

```
Scheduler / API / CLI
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│                     LANGGRAPH PIPELINE                          │
│                                                                 │
│  Data Collector ──► Data Quality                                │
│                          │                                      │
│                   [quality gate] ──► (abort on invalid data)    │
│                          │                                      │
│                    Orchestrator ──► Analyst ──► RAG Agent       │
│                                                      │          │
│                                                   Writer        │
│                                                      │          │
│                                                 Evaluator ◄──┐  │
│                                                      │       │  │
│                                              [score loop ≤3]─┘  │
│                                                      │          │
│                                                  Delivery       │
│                                                      │          │
│                                                  Feedback       │
└─────────────────────────────────────────────────────────────────┘
```

| Agent | Responsibility |
|---|---|
| **Data Collector** | Queries MySQL/SQLite, packages raw data for the period |
| **Data Quality** | Null checks, outliers, date consistency — gates the pipeline |
| **Orchestrator** | Builds the analysis plan and routes the run |
| **Analyst** | Trends, anomalies, forecasts, category/sector performance |
| **RAG Agent** | Retrieves context from past reports (ChromaDB) |
| **Writer** | Generates the executive report via LLM (zero-shot / few-shot / CoT) |
| **Evaluator** | Scores quality and triggers revisions until approved |
| **Delivery** | Sends the report over SMTP and/or WhatsApp |
| **Feedback** | Records run metrics for later personalisation |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Multi-agent | LangGraph 0.2+ / LangChain 0.3+ |
| LLM | OpenAI GPT-4o |
| RAG | ChromaDB + `text-embedding-3-small` |
| Database | SQLite (dev) / MySQL 8.0 (prod), SQLAlchemy 2.0 |
| Analysis | pandas, numpy, scikit-learn, statsmodels, scipy, prophet, pymannkendall |
| Reporting | Jinja2, python-docx, matplotlib, plotly |
| API | FastAPI + uvicorn, JWT (python-jose), bcrypt |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS 4, Recharts |
| Scheduler | APScheduler |
| Delivery | SMTP, Twilio WhatsApp |
| Container | Docker + Docker Compose |
| Observability | LangSmith (optional) |

---

## Quick Start

### Option A — SQLite, no Docker

```bash
git clone git@github.com:Ediz-Ural/proactive-reporting-agent.git
cd proactive-reporting-agent

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

cp .env.example .env             # OPENAI_API_KEY is optional, see "API keys" below

python data/seed_db.py --generate    # 5,000 synthetic rows + demo companies/users
python data/seed_reports.py          # optional: index sample reports into ChromaDB

pytest -q                        # run the test suite
uvicorn src.api:app --reload     # API on http://localhost:8000
```

Frontend, in a second terminal:

```bash
cd frontend
npm install
npm run dev                      # http://localhost:5173
```

### Option B — Docker Compose (MySQL + API + frontend + Adminer)

```bash
cp .env.example .env             # set DB_TYPE=mysql and a DB_PASSWORD
docker compose up -d
docker compose exec app python data/seed_db.py --generate
```

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| API docs | http://localhost:8000/docs |
| Adminer | http://localhost:8080 |

### Demo credentials

`seed_db.py` creates demo accounts for local use only — change or remove them before
deploying anywhere real.

| Role | Email | Password |
|---|---|---|
| Admin | `admin@superstore.com` | `admin123` |
| Company user | `user@<company-domain>` | `user123` |

### API keys

Every user brings their own OpenAI credentials. Enter a key and pick a model
under **Ayarlar** (Settings) in the dashboard: the key is kept in that browser's
`localStorage` and sent as an `X-OpenAI-Key` header on the requests that run the
pipeline. The server uses it for that run and never writes it to disk, so no key
of yours ends up in the database, the logs, or a backup.

`OPENAI_API_KEY` in `.env` is an optional fallback for runs that have no user
behind them — the scheduler, `scripts/`, and direct `run_pipeline` calls. With
neither a header nor an env key the pipeline still runs, but the LLM steps
(writer, evaluator) are skipped.

### Dataset

The seeder generates synthetic data by default. To use the Kaggle *Sample Superstore*
dataset instead, download it yourself and point the seeder at it — it is not redistributed
in this repository:

```bash
python data/seed_db.py --csv data/raw/superstore.csv
```

---

## Usage

### Run the pipeline in Python

```python
from src.graph.workflow import run_pipeline

state = run_pipeline(
    start_date="2017-06-01",
    end_date="2017-06-30",
    report_type="monthly",
    company_id=1,
    api_key="sk-...",      # optional; falls back to OPENAI_API_KEY
    model="gpt-4o-mini",   # optional; falls back to OPENAI_MODEL
)
print(state["final_report"])
```

### Key API endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/login` | Obtain a JWT |
| `POST` | `/run` | Trigger a pipeline run in the background (accepts `X-OpenAI-Key`) |
| `POST` | `/run/monthly` | Run for a given month |
| `POST` | `/run/sync` | Run and wait for the result |
| `GET` | `/runs`, `/runs/{id}` | Run history and status |
| `GET` | `/reports`, `/reports/{filename}` | List and fetch generated reports |
| `GET` | `/db/stats`, `/rag/stats` | Data and vector-store statistics |
| `POST` | `/admin/upload-data` | Upload a CSV for a company (admin) |
| `POST` | `/admin/companies` | Tenant administration (admin) |
| `POST` | `/admin/send-report` | Deliver a report manually (admin) |

Interactive documentation is at `/docs`.

### Scripts

```bash
python scripts/batch_generate.py --start 2017-01     # generate reports for all companies
python scripts/ab_test.py --runs 3 --company-id 1    # compare prompting strategies
python scripts/pattern_comparison.py --runs 5        # prompt chaining vs. multi-agent
```

Results are written to `data/ab_test/`, `data/pattern_comparison/`, and `data/metrics/`
(all git-ignored).

---

## Project Structure

```
proactive-reporting-agent/
├── config/            # Pydantic settings + logging config
├── data/              # seed_db.py, seed_reports.py, sample reports, generated artefacts
├── src/
│   ├── agents/        # one file per agent
│   ├── tools/         # sql, analysis, rag, report, llm tools
│   ├── graph/         # LangGraph state + workflow DAG
│   ├── models/        # Pydantic schemas
│   ├── api.py         # FastAPI app
│   ├── auth.py        # JWT auth
│   └── scheduler.py   # APScheduler job
├── frontend/          # React + TypeScript dashboard
├── scripts/           # batch generation and experiments
├── templates/         # Jinja2 HTML report template
├── tests/             # pytest suite
├── docker-compose.yml
└── pyproject.toml
```

---

## Configuration

All settings come from environment variables or `.env` (see `.env.example`).

| Variable | Default | Description |
|---|---|---|
| `DB_TYPE` | `sqlite` | `sqlite` or `mysql` |
| `SQLITE_PATH` | `data/reporting_agent.db` | SQLite file path |
| `DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASSWORD` / `DB_NAME` | — | MySQL connection |
| `OPENAI_API_KEY` | — | Optional fallback; users supply their own key in the UI |
| `OPENAI_MODEL` | `gpt-4o` | Default model when the user picks none |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding model |
| `CHROMA_PERSIST_DIR` | `data/chroma` | Vector store location |
| `WRITER_STRATEGY` | `few_shot` | `zero_shot` / `few_shot` / `cot` |
| `MAX_EVALUATOR_ITERATIONS` | `3` | Writer→Evaluator revision limit |
| `JWT_SECRET_KEY` | placeholder | **Must be changed for any real deployment** |
| `SMTP_*`, `REPORT_RECIPIENTS` | — | Email delivery |
| `TWILIO_*`, `WHATSAPP_*` | — | Optional WhatsApp delivery |
| `SCHEDULER_ENABLED` | `false` | Enable the monthly job |
| `LANGCHAIN_*` | — | Optional LangSmith tracing |

Never commit a real `.env` — it is git-ignored.

---

## Testing

```bash
pytest -q                    # full suite
pytest --cov=src -q          # with coverage
ruff check .                 # lint
```

CI runs the backend lint + tests and the frontend lint + build on every push and pull request.

---

## Experiment Design

The project compares agentic design patterns on the same dataset:

| Pattern | Description |
|---|---|
| Prompt chaining | Baseline — sequential LLM calls |
| Orchestrator-workers | Central coordinator + specialised workers |
| + Evaluator-optimizer | Adds the quality feedback loop (this architecture) |

Each pattern is run with several context strategies (zero-shot, few-shot, chain-of-thought)
and scored on report quality, latency, and token cost by the Evaluator agent.

---

## License

MIT — see [LICENSE](LICENSE).
