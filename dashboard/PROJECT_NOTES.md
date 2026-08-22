# AutoApply-JobHunter Dashboard — scaffold notes

Angular 21 (LTS), standalone components, zoneless by default, `@ngrx/signals` SignalStore. Built to
the architecture blueprint: feature-driven folders, Container/Presentational
split, REST for state + WebSocket reserved for the Executor phase only.

## Run it

```
npm install
npx ng serve
```

Open http://localhost:4200. You'll see real data immediately — it's
served by `mockApiInterceptor`, not a live backend (there is no backend
yet). Two routes: `/pipeline` (Kanban board across all `JobStatus`
values) and `/review` (borderline-score approve/reject queue).

## What's real vs. stubbed

| Piece | Status |
|---|---|
| Folder structure, standalone components, `@if`/`@for` | Real |
| `PipelineStore` (SignalStore) | Real, works against mock data now |
| `JobReviewCardComponent`, `ExecutionTerminalComponent`, `StatusBadgeComponent` | Real, fully functional |
| `JobApiService` (REST) | Real HTTP calls — but `/api/jobs` doesn't exist server-side yet |
| `JobSocketService` (WebSocket) | Real client code — `/ws/executor/{id}` doesn't exist server-side yet |
| `mockApiInterceptor` | Temporary — delete once the FastAPI service is live |

## What the backend needs to add

The Python repo (`app/db/models.py`) already has the `Job` / `JobStatus`
shape this expects — field names in `core/models/job.model.ts` mirror
it 1:1 (camelCase vs snake_case aside). Two gaps to close before the
mock interceptor can come out:

1. **No HTTP layer exists at all yet.** This needs a FastAPI service
   wrapping the existing SQLAlchemy session — `GET /api/jobs`,
   `GET /api/jobs/{id}`, `PATCH /api/jobs/{id}/status` at minimum.
2. **No rationale is persisted.** `app/llm/base.py`'s `EvaluationResult`
   already has a `reasoning: str` from the LLM, but
   `app/evaluator.py` only writes `match_score` onto the `Job` row —
   the reasoning text itself is discarded. `JobReviewCardComponent`
   needs it to be useful; either add a `rationale` column or a side
   table keyed by `job_id`.
3. **No WebSocket/SSE endpoint yet** for `JobSocketService` to connect
   to — `/ws/executor/{job_id}` streaming `runner.py`'s progress events,
   plus handling the `{action: 'kill', jobId}` message from the kill
   switch in `ExecutionTerminalComponent`.

## Folder structure

```
src/app/
  core/           singletons: HTTP interceptors, WebSocket service, error log
  shared/         StatusBadge, ExecutionTerminal, LpaCurrency pipe
  features/
    pipeline/     PipelineStore (SignalStore) + Kanban container
    review/       JobReviewCard (presentational) + review queue container
```
