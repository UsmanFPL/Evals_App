# Windsurf Execution Plan: AI Evaluation & Management Platform

> This document decomposes the *AI_Evaluation_Platform_Plan.md* into very small, sequential tasks that a coding agent (Cascade) can follow with minimal ambiguity.  The tasks are organised into phases; **Phase-1 delivers a fully-functional local MVP** (single-machine, Docker Compose) capable of running end-to-end evaluations using the existing `evaluate_overviews.py` core logic. Later phases incrementally add enterprise features.

---

## Legend  
`[B]` = Backend (Python/FastAPI) `[F]` = Frontend (Next.js) `[W]` = Worker (Celery) `[I]` = Infrastructure / DevOps `[DB]` = Database / Migrations

Each task has an **ID** so future PRs / agent prompts can reference them.

---

## Phase-0  –  Bootstrap (Day 0-1)
| ID | Task | Details |
|----|------|---------|
| P0-1 [I] | Initialise Git repo | Create repo root with MIT licence, `.gitignore`, `README`. |
| P0-2 [I] | Create mono-repo structure | Folders: `/services/api`, `/services/worker`, `/frontend`, `/infra` (Docker), `/docs`, `/scripts`. |
| P0-3 [I] | Add root `pyproject.toml` with Poetry | Common deps: `fastapi`, `uvicorn`, `pydantic`, `celery`, `pandas`, `sqlalchemy`, `asyncpg`, `python-dotenv`. |
| P0-4 [I] | Docker Compose skeleton | Services: `api`, `worker`, `postgres`, `redis`, `frontend`. Expose ports 8000 (API), 3000 (UI), 5432, 6379. |
| P0-5 [DB] | Provision Postgres init script | Create empty database `evals`; mount to `/docker-entrypoint-initdb.d`. |
| P0-6 [I] | CI workflow scaffold | GitHub Actions: lint (ruff), test, build Docker images. |

Deliverable: running `docker compose up` shows healthy containers (no app logic yet).

---

## Phase-1  –  Local MVP (Week 1-2)
Goal: Execute *upload dataset → trigger run → view results* on localhost.

### 1. Data Layer
| ID | Task |
|----|------|
| P1-DL-1 [DB] | Define minimal tables via Alembic migration: `projects`, `datasets`, `runs`, `results`. |
| P1-DL-2 [B] | Add SQLAlchemy models & Pydantic schemas. |

### 2. Backend API
| ID | Task | Endpoint |
|----|------|----------|
| P1-API-1 [B] | FastAPI application factory in `services/api/main.py`. | – |
| P1-API-2 [B] | `POST /projects` – create project. | Validate name. |
| P1-API-3 [B] | `POST /datasets/upload` – multipart CSV upload. | Store file to local volume `data/`, insert row. |
| P1-API-4 [B] | `POST /runs` – trigger Celery job. | Body: `{project_id, dataset_id, model_name, prompt_text}`. Returns `run_id`. |
| P1-API-5 [B] | `GET /runs/{id}` – return status + aggregate scores. | Polling support. |
| P1-API-6 [B] | `GET /results` – filter by `run_id`, paginate. |
| P1-API-7 [B] | Add simple token auth (fastapi-http-auth) – static API key in `.env`. |

### 3. Evaluation Worker
| ID | Task | Details |
|----|------|---------|
| P1-W-1 [W] | Copy `evaluate_overviews.py` into `services/worker/core/`. | Refactor into modules: `context.py`, `prompt.py`, `llm.py`, `evaluate.py`. |
| P1-W-2 [W] | Celery app & task `run_evaluation(run_id)` that:  
1. Loads dataset & prompt from DB.  
2. Executes evaluation over rows using refactored core logic.  
3. Writes per-row `results` and aggregate JSON to DB. |
| P1-W-3 [W] | Store raw LLM response & latency in `results`. |
| P1-W-4 [W] | Commit retry/back-off settings via env vars. |

### 4. Frontend (Minimal)
| ID | Task | Page | Function |
|----|------|------|----------|
| P1-F-1 [F] | Setup Next.js 14 app with Tailwind. | – |
| P1-F-2 [F] | `.env.local` with `NEXT_PUBLIC_API_URL`. | – |
| P1-F-3 [F] | Wizard page `/wizard` (3 steps):  
1. Project name  
2. Upload CSV (input/output)  
3. Prompt editor (textarea). |
| P1-F-4 [F] | Trigger `/runs` and redirect to `/runs/[id]`. |
| P1-F-5 [F] | Run page polls `/runs/{id}`; progress bar. |
| P1-F-6 [F] | Results table using `react-table`, shows input, output, faithfulness score, etc. |

### 5. Dev & DX
| ID | Task |
|----|------|
| P1-DX-1 [I] | Hot-reload with `uvicorn --reload` and `next dev`. |
| P1-DX-2 [I] | Pre-commit hooks: ruff, black, isort. |
| P1-DX-3 [I] | Sample fixture data + Makefile `make demo` to auto-upload dummy CSV and run eval. |

**Exit-Criteria Phase-1**  
`make demo` spins up Docker Compose, opens http://localhost:3000, user uploads sample CSV + prompt, clicks **Run**, sees scores in table within minutes.

---

## Phase-2  –  Enhanced Metrics & Assistant (Week 3-4)
| ID | Task | Notes |
|----|------|-------|
| P2-M-1 [W] | Metric plugin interface `services/metrics/base.py`. |
| P2-M-2 [W] | Implement BLEU, ROUGE, BERTScore plugins. |
| P2-M-3 [B] | `/metrics` endpoints to list & register custom metric (upload code snippet). |
| P2-A-1 [W] | AI Assistant endpoints `/assist/generate_tests`, `/assist/suggest_metrics`. |
| P2-A-2 [F] | UI buttons “Generate 50 test cases”, “Suggest metrics” in wizard. |
| P2-D-1 [F] | Dashboard charts with ECharts: accuracy over runs, leaderboard. |

---

## Phase-3  –  Regression & CI/CD (Week 5-6)
| ID | Task |
|----|------|
| P3-R-1 [DB] | Add `baseline_run_id` column to `projects`. |
| P3-R-2 [W] | Worker computes diff vs baseline, flags regressions. |
| P3-R-3 [B] | GitHub webhook endpoint `/ci` to accept `project`, `sha`, trigger run. |
| P3-R-4 [F] | Dashboard view *Regressions* (red/green highlighting). |
| P3-R-5 [I] | Slack & GitHub PR comment integrations via incoming webhooks. |

---

## Phase-4  –  Enterprise Features (Week 7-8)
| ID | Task |
|----|------|
| P4-S-1 [B] | Integrate Auth0 OIDC login (SSO). |
| P4-S-2 [B] | Role-based access control middleware. |
| P4-S-3 [DB] | `organizations`, `users`, `audit_logs` tables. |
| P4-S-4 [F] | Org switcher in UI header. |
| P4-S-5 [I] | GDPR data-export command. |

---

## Phase-5  –  Advanced Analytics (Week 9-10)
| ID | Task |
|----|------|
| P5-C-1 [W] | Nightly embedding job, store `input_emb` in `results`. |
| P5-C-2 [W] | KMeans clustering & cache groups. |
| P5-C-3 [F] | Heatmap & cluster explorer pages. |
| P5-RC-1 [W] | Root-cause analyser service surfacing common error tags. |

---

## Phase-6  –  Hardening & Scale (Week 11-12)
| ID | Task |
|----|------|
| P6-H-1 [I] | Migrate evaluation workers to Kubernetes with HPA. |
| P6-H-2 [I] | Add Redis cache for LLM responses. |
| P6-H-3 [I] | Add Prometheus metrics endpoints & Grafana dashboards. |
| P6-H-4 [I] | Load/performance test 100k test-cases run. |

---

## Appendix A – Suggested Task Execution Order
Within each phase, tackle tasks top-to-bottom because later steps depend on earlier foundations.

---

*Document generated: 2025-06-15*
