# AI Evaluation & Management Platform for LLMs – Detailed Implementation Plan

> *This document translates the product specification into a concrete, actionable engineering plan.  It re-uses the core logic from `evaluate_overviews.py` (prompt construction, row-wise evaluation, retry/back-off, parallel execution) and extends it into a production-grade, web-based platform.*

---

## 1. Goals & Non-Goals
|                       | In-scope (v1-v2)                                       | Out-of-scope (future/optional)                         |
|-----------------------|---------------------------------------------------------|--------------------------------------------------------|
| Automated & human-in-the-loop evaluation | ✅ Batch scoring via OpenAI, ✅ Metric library, ✅ Human feedback UI | ❌ RLHF fine-tuning, ❌ active learning pipelines |
| Regression tracking   | ✅ Versioned runs, ✅ Baseline comparison, ✅ CI hooks       | ❌ Full MLOps model deployment                        |
| Integrations          | ✅ Slack, GitHub PR comment, CSV/PDF export               | ❌ PagerDuty, ❌ ServiceNow                            |
| Security/Compliance   | ✅ SSO (OAuth/OIDC), ✅ audit log, ✅ encryption at rest     | ❌ FedRAMP, ❌ on-prem air-gapped install             |

## 2. High-Level Architecture
```
┌────────────┐   REST/WS    ┌──────────────┐   AMQP/Redis   ┌──────────────┐
│  Frontend  │◀────────────▶│  API Server  │◀──────────────▶│  Worker Pool │
│  (React)   │              │ (FastAPI)    │                │  (Celery)    │
└────────────┘              └──────────────┘                └──────────────┘
       ▲                          ▲   ▲                              ▲
       │ GraphQL (future)         │   │ Webhooks                     │
       │                          │   │                              │
┌──────┴──────┐              ┌────┴───┴────┐                 ┌────────────┐
│ Postgres +  │◀────────────▶│  Metrics     │                 │  Object    │
│  Timescale  │              │  Service    │                 │  Storage   │
└─────────────┘              └─────────────┘                 └────────────┘
```
* Deployed via Docker / Kubernetes; each component is stateless, enabling horizontal scaling.
* API Server orchestrates jobs, handles auth, emits events; Worker Pool executes long-running LLM evaluations using logic adapted from `evaluate_overviews.py`.

## 3. Component Breakdown
### 3.1 Frontend (Next.js + TypeScript)
| Page / View                 | Purpose                                                     |
|-----------------------------|-------------------------------------------------------------|
| `/wizard`                   | Step-by-step Use-Case definition (task → data → metrics)    |
| `/suite/:id`                | Visual Test Suite: spreadsheet view w/ filters, annotations |
| `/dashboard/:id`            | Time-series & leaderboards                                  |
| `/settings/integrations`    | Slack, GitHub, Jira tokens                                  |
| `/admin` (enterprise)       | Tenant & role management                                    |

### 3.2 API Server (FastAPI)
* Handles REST endpoints, JWT/SSO auth, RBAC.
* Validates uploads, stores metadata, places tasks on Celery queue.
* Exposes **/runs/** endpoints for CI integration (`POST /runs?project=XYZ`).

### 3.3 Evaluation Worker Service
Re-implements and generalises `evaluate_overviews.py`:
1. **Data Loading** – reads `knowledge_df`, `model_df` from S3/object storage or DB.
2. **Context Builder** – uses `build_context` unchanged ➜ moves to `services/prompting/context.py`.
3. **Prompt Builder** – wraps `build_prompt` with Jinja templates for different metric sets.
4. **LLM Call** – retains `call_llm` with retry/back-off; configurable model, rate-limit, caching.
5. **Row Processor** – mirrors `process_single_row`; outputs `EvaluationResult` pydantic model.
6. **Parallel Execution** – ThreadPool or AsyncIO; concurrency parameterised per worker pod.

### 3.4 Metrics Service
* Library in `services/metrics/` with plugin pattern (`EntryPoints`):
    ```python
    class Metric(Protocol):
        id: str
        name: str
        def compute(pred: str, ref: str | None, **ctx) -> float: ...
    ```
* Built-in plugins: BLEU, ROUGE, BERTScore, toxicity (Perspective API), length, latency.
* Custom Python metric uploads via UI; stored in `metric_definitions` table.

### 3.5 AI Assistant Service
* Lightweight wrapper around OpenAI ChatCompletion.
* Prompts stored in `assistant_templates/`.
* Used for **Synthetic Test Gen** & **Metric Suggestion**.

### 3.6 Database Schema (Postgres)
```
organizations(id PK, name, tier, created_at)
users(id PK, org_id FK, email, role, sso_sub, …)
projects(id PK, org_id FK, name, description, …)
model_versions(id PK, project_id, name, provider, params, created_at)
 datasets(id PK, project_id, csv_path, schema, created_at)
 test_cases(id PK, dataset_id, input_text, expected_output, tags[])
 prompts(id PK, project_id, text, version, metadata JSONB)
 runs(id PK, project_id, model_version_id, prompt_id, status, started_at, …)
 results(id PK, run_id, test_case_id, raw_output, latency_ms, metrics JSONB)
 feedback(id PK, result_id, user_id, rating INT, comment TEXT)
 metrics(id PK, name, code, description, owner_id)
 audit_logs(id PK, user_id, action, object, timestamp)
```
TimescaleDB hypertables on `results` for fast time-series queries.

## 4. API Endpoints (excerpt)
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/projects` | Create project |
| `POST` | `/datasets/upload` | Upload CSV, returns `dataset_id` |
| `POST` | `/runs` | Trigger evaluation run |
| `GET`  | `/runs/{id}` | Run status & aggregated scores |
| `GET`  | `/results` | Paginated test-case results w/ filters |
| `POST` | `/feedback` | Submit human rating |

## 5. Data Flow (Run Execution)
1. **Trigger** – via UI button or CI webhook (`POST /runs`).
2. **API** writes `run` row = `PENDING`, enqueues Celery task with IDs.
3. **Worker** fetches dataset, prompt, model params → iterates rows (parallel), using core logic.
4. Metrics computed & stored per row; partial progress heartbeat every *n* rows.
5. On completion, aggregate metrics saved; Slack/GitHub webhook fired.

## 6. Dashboards & Analytics Implementation
* **Backend** aggregates via SQL (GROUP BY) + materialised views.
* **Frontend** uses [Apache ECharts] for charts; `react-table` for grid.
* Embedding-driven clustering: nightly job writes `input_emb` using OpenAI `/embeddings`; k-means; clusters cached.

## 7. Security & Compliance
* OAuth / SAML SSO via Auth0.
* Role matrix: `Owner`, `Editor`, `Viewer` per project.
* Column-level encryption on sensitive text (`pgcrypto`).
* Audit log middleware captures all mutations.
* Network: private subnets; VPC endpoints for OpenAI.

## 8. DevOps
| Area | Tooling |
|------|---------|
| Container build | Docker + GitHub Actions CI |
| Orchestration | Kubernetes (AWS EKS) |
| Secrets | AWS Secrets Manager |
| Observability | Prometheus + Grafana; Sentry for app errors |
| Cost control | Per-run token estimation; alert if > budget |

## 9. Roadmap & Milestones
| Phase | Duration | Deliverables |
|-------|----------|--------------|
| **0 – Bootstrap** | 1 wk | Repo, CI, Docker skeleton; port `evaluate_overviews.py` into service |
| **1 – MVP** | 4 wks | Upload CSV, run evaluations, basic dashboard, Slack alert |
| **2 – Assistant + Metrics** | 3 wks | Synthetic test gen, custom metric plugins, GitHub PR report |
| **3 – Regression & CI** | 2 wks | Baseline diff, CI blocking, Jira integration |
| **4 – Enterprise** | 4 wks | SSO, RBAC, audit logs, multi-tenant scaling |
| **5 – Advanced Analytics** | 3 wks | Clustering, root-cause, embedding explorer |

## 10. Risks & Mitigations
* **LLM API cost spikes** → caching + concurrency limits.
* **Rate limits** → exponential back-off (already in script), queue throttling.
* **Data privacy** → optional on-prem/self-host install.
* **Metric bias / correctness** → open-source metric library, unit tests.

## 11. Test Strategy
* **Unit tests** for each metric & API endpoint.
* **Integration tests** spin up ephemeral Postgres + worker.
* **Load tests** using Locust for 10k test-cases.
* **Security tests** – OIDC flow, RBAC checks.

## 12. Reusing `evaluate_overviews.py`
| Script Function | Platform Mapping |
|-----------------|------------------|
| `load_csv`      | Part of Data Ingestion service (`services/data/loaders`) |
| `build_context` | Prompt Context Builder micro-module |
| `build_prompt`  | Templated Prompt Engine (`services/prompting/templates`) |
| `call_llm` + retry | Shared `utils/llm.py` wrapper (global)
| `process_single_row` | Worker task for one `TestCaseEvaluation` |
| `evaluate_rows` | Celery task executing batch, streaming progress |

Code will be refactored into Pydantic models and reusable utilities, ensuring clean separation of concerns while preserving proven logic.

## 13. Glossary
* **Test Case** – `(input_text, expected_output, meta)` row.
* **Run** – Execution of *n* test cases against *(model, prompt)* pair.
* **Metric** – Function returning score(s) given `pred, ref, context`.
* **Baseline** – Previously selected `run_id` used for regression diff.

---
*Document version: 2025-06-15*
