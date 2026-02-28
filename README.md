# Proactive Reporting Agent

A multi-agent AI system that automatically collects data from a database, analyses trends and anomalies, generates executive reports, and proactively delivers them to decision-makers.

> **Status:** Week 1 complete — data layer, SQL tools, Data Collector + Data Quality agents functional.

---

## Architecture

```
Scheduler
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│                     LANGGRAPH PIPELINE                          │
│                                                                 │
│  Orchestrator ──► Data Collector ──► Data Quality              │
│                                           │                     │
│                                    [quality gate]               │
│                                           │                     │
│                                       Analyst ──► RAG Agent    │
│                                                        │        │
│                                                     Writer      │
│                                                        │        │
│                                                   Evaluator ◄──┐│
│                                                        │       ││
│                                               [score loop ≤3]  ││
│                                                        │       ┘│
│                                                   Delivery      │
│                                                        │        │
│                                                    Feedback     │
└─────────────────────────────────────────────────────────────────┘
```

### Agent Responsibilities

| Agent | Week | Responsibility |
|---|---|---|
| **Orchestrator** | 2 | Coordinates the pipeline, handles routing |
| **Data Collector** | 1 ✅ | Queries MySQL/SQLite, packages raw data |
| **Data Quality** | 1 ✅ | Null checks, outliers, date consistency |
| **Analyst** | 2 | Trend, anomaly, forecasting (Python tools) |
| **RAG Agent** | 3 | Retrieves past report context (ChromaDB) |
| **Writer** | 3 | Generates executive summary via LLM |
| **Evaluator** | 4 | Scores report quality, triggers revisions |
| **Delivery** | 4 | Sends report via SMTP |
| **Feedback** | 5 | Tracks opens/clicks for personalisation |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Multi-Agent | LangGraph 0.2+ |
| LLM | OpenAI GPT-4o (or Claude Sonnet) |
| RAG | ChromaDB + text-embedding-3-small |
| Database | SQLite (dev) / MySQL 8.0 (prod) |
| ORM | SQLAlchemy 2.0 |
| Data | pandas, numpy |
| Stats/ML | scikit-learn, statsmodels, scipy, prophet |
| Reporting | Jinja2, python-docx, matplotlib, plotly |
| API | FastAPI + uvicorn |
| Scheduler | APScheduler |
| Delivery | SMTP |
| Config | Pydantic Settings |
| Container | Docker + Docker Compose |
| Observability | LangSmith (optional) |

---

## Project Structure

```
proactive-reporting-agent/
├── config/
│   ├── settings.py          # Pydantic Settings (all env vars)
│   └── logging_config.py    # Centralised logging setup
│
├── data/
│   ├── raw/                 # Place Superstore CSV here
│   ├── processed/           # Cleaned data output
│   └── seed_db.py           # CSV → DB loader (or synthetic data generator)
│
├── src/
│   ├── agents/              # One file per agent
│   │   ├── data_collector.py  ← Week 1 complete
│   │   ├── data_quality.py    ← Week 1 complete
│   │   ├── orchestrator.py    (stub)
│   │   ├── analyst.py         (stub)
│   │   ├── rag_agent.py       (stub)
│   │   ├── writer.py          (stub)
│   │   ├── evaluator.py       (stub)
│   │   ├── delivery.py        (stub)
│   │   └── feedback.py        (stub)
│   │
│   ├── tools/
│   │   ├── sql_tools.py       ← Week 1 complete
│   │   ├── analysis_tools.py  ← Week 1 complete
│   │   ├── rag_tools.py       (stub)
│   │   └── report_tools.py    (stub)
│   │
│   ├── models/
│   │   └── schemas.py         # Pydantic data contracts
│   │
│   ├── graph/
│   │   ├── state.py           # LangGraph AgentState TypedDict
│   │   └── workflow.py        # LangGraph DAG definition
│   │
│   └── utils/
│       └── helpers.py         # Misc utilities
│
├── templates/
│   └── report_template.html   # Jinja2 template (Week 3)
│
├── tests/
│   ├── test_data_collector.py  ← Week 1 complete
│   ├── test_data_quality.py    ← Week 1 complete
│   └── test_analysis_tools.py  ← Week 1 complete
│
├── notebooks/
│   └── exploration.ipynb
│
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
└── .env.example
```

---

## Quick Start

### Option A — SQLite (no Docker required)

```bash
# 1. Clone and create virtual environment
git clone <repo-url>
cd proactive-reporting-agent
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -e ".[dev]"

# 3. Copy environment template
cp .env.example .env
# DB_TYPE is already 'sqlite' by default — no changes needed

# 4. Seed the database (generates 5 000 synthetic rows)
python data/seed_db.py --generate

# OR if you have the Kaggle Superstore CSV:
# python data/seed_db.py --csv data/raw/superstore.csv

# 5. Run tests
pytest -v
```

### Option B — MySQL via Docker

```bash
# 1. Copy and configure .env
cp .env.example .env
# Set DB_TYPE=mysql, DB_PASSWORD=secret (or your own)

# 2. Start services
docker compose up -d

# 3. Seed the database
docker compose exec app python data/seed_db.py --generate

# 4. Run tests inside container
docker compose exec app pytest -v

# 5. Adminer DB UI → http://localhost:8080
#    Server: mysql  |  User: reporter  |  Password: secret  |  DB: reporting_agent
```

---

## Running the Pipeline

```python
from src.graph.workflow import run_pipeline

state = run_pipeline(
    start_date="2024-01-01",
    end_date="2024-01-07",
    report_type="weekly",
)
print(state["weekly_summary"])
```

### Using Data Collector directly

```python
from src.agents.data_collector import DataCollectorAgent

agent = DataCollectorAgent()
data = agent.collect("2024-01-01", "2024-01-31")

print(data["weekly_summary"])
# {'period': '2024-01-01 to 2024-01-31', 'total_revenue': 12340.5, ...}
```

### Validating data quality

```python
from src.agents.data_quality import DataQualityAgent

qa = DataQualityAgent()
report = qa.validate(data)

print(report["is_valid"])      # True / False
print(report["warnings"])      # ['Column X has 6.2% nulls', ...]
print(report["errors"])        # []
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DB_TYPE` | `sqlite` | `sqlite` or `mysql` |
| `DB_HOST` | `localhost` | MySQL host |
| `DB_PORT` | `3306` | MySQL port |
| `DB_USER` | `root` | DB username |
| `DB_PASSWORD` | `` | DB password |
| `DB_NAME` | `reporting_agent` | Database name |
| `SQLITE_PATH` | `data/reporting_agent.db` | SQLite file path |
| `OPENAI_API_KEY` | `` | Required for Week 2+ (LLM agents) |
| `OPENAI_MODEL` | `gpt-4o` | LLM model ID |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding model |
| `CHROMA_PERSIST_DIR` | `data/chroma` | ChromaDB storage |
| `MAX_EVALUATOR_ITERATIONS` | `3` | Max Writer→Evaluator loops |
| `SMTP_HOST` | `` | SMTP server (Week 4) |
| `REPORT_RECIPIENTS` | `` | Comma-separated emails |

---

## Weekly Progress

| Week | Goal | Status |
|---|---|---|
| **1** | Infrastructure, data layer, Data Collector + Quality agents | ✅ Complete |
| **2** | Analyst Agent (trend/anomaly/forecast), LangGraph full DAG | 🔜 |
| **3** | RAG Agent (ChromaDB), Writer Agent (LLM), report templates | 🔜 |
| **4** | Evaluator Agent, Delivery Agent (SMTP), FastAPI endpoint | 🔜 |
| **5** | Feedback Agent, pattern comparison experiment, evaluation metrics | 🔜 |

---

## Academic Experiment Design

This project compares four agentic design patterns on the same dataset:

| Pattern | Description |
|---|---|
| Prompt Chaining | Baseline — sequential LLM calls |
| Orchestrator-Workers | Central coordinator + specialised workers |
| +Evaluator-Optimizer | Adds quality feedback loop (current architecture) |
| +Parallelization | Voting ensemble across parallel writer instances |

Each pattern is evaluated with five context strategies (Zero-shot, Few-shot, CoT, ReAct, ToT) using ROUGE-L, BERTScore, hallucination rate, latency, and token cost as metrics.

---

## License

MIT — see `LICENSE` for details.
