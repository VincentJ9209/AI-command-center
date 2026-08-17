# AI-command-center Task 8B Background Execution Design

**Date:** 2026-08-17  
**Status:** Approved design baseline; ready for repository review and commit  
**Branch:** `feat/background-execution`

## Purpose

Task 8B removes OpenAI execution from the LINE webhook request lifecycle while preserving the existing routing, persistence, approval, task lifecycle, and notification behavior delivered in Tasks 1–8A.

The webhook must persist an executable task, acknowledge the LINE request, enqueue only the task ID, and return HTTP 200 without waiting for OpenAI. A background worker then reconstructs all required state from durable storage, executes the task, persists the terminal state, and sends the final LINE notification.

## Goals

- Introduce a replaceable `JobDispatcher` abstraction.
- Implement a process-local dispatcher backed by `ThreadPoolExecutor`.
- Pass only `task_id: str` across the dispatch boundary.
- Ensure every background job creates and closes its own SQLAlchemy session.
- Keep `TaskExecutionService` as the core execution service.
- Persist the LINE push destination required by a task-ID-only worker.
- Make duplicate dispatch safe so one task is not executed by OpenAI more than once.
- Allow a persisted `RECEIVED` task to be re-dispatched after a transient enqueue failure.
- Keep `WAITING_APPROVAL` / `ACTION_REQUIRED` tasks outside the background executor.
- Preserve a migration path to Cloud Tasks or Pub/Sub without rewriting execution logic.

## Non-goals

Task 8B does not add Cloud Tasks, Pub/Sub, Celery, Redis, RQ, Kafka, RabbitMQ, distributed worker deployment, task scheduling, task priorities, task cancellation, a dead-letter queue, automatic exponential-backoff retries, a transactional notification outbox, dashboard functionality, or an approval workflow redesign.

## Architecture

```text
LINE webhook
  -> verify signature
  -> parse and route
  -> persist task
  -> send ACK
  -> dispatch(task_id)
  -> HTTP response

LocalJobDispatcher
  -> ThreadPoolExecutor
  -> TaskJobWorker.run(task_id)

TaskJobWorker
  -> create DB session
  -> load/claim task
  -> TaskExecutionService
  -> persist COMPLETED / FAILED
  -> LINE push DONE / FAILED
  -> close DB session
```

The dispatch boundary is intentionally small:

```python
class JobDispatcher(Protocol):
    def dispatch(self, task_id: str) -> None:
        ...
```

The dispatcher must never receive a SQLAlchemy `Session`, ORM `Task`, `LineTextMessage`, FastAPI `Request`, or request-scoped dependency object.

## Component Boundaries

### `app/jobs/dispatcher.py`

Defines `JobDispatcher` and the dispatcher-level error contract. It has no FastAPI or SQLAlchemy dependency.

### `app/jobs/local.py`

Implements `LocalJobDispatcher` with `ThreadPoolExecutor`. Its responsibilities are limited to accepting `task_id`, submitting `worker.run(task_id)`, observing/logging future exceptions, rejecting dispatch after shutdown, and shutting down the executor during application shutdown.

### `app/jobs/worker.py`

Defines `TaskJobWorker`. It owns the background session lifecycle and depends on a session factory, `AIProvider`, and `NotificationService`. It reloads the task by ID, claims it for execution, invokes `TaskExecutionService`, sends DONE/FAILED push notifications using durable task source metadata, logs notification failures without rewriting the task execution result, and always closes its session.

### `app/tasks/executor.py`

Remains the core application execution service, but its entry precondition changes: it receives a task that has already been successfully claimed and is already `RUNNING`. It creates the `AIExecutionRequest`, calls `AIProvider`, and persists only the terminal `RUNNING -> COMPLETED` or `RUNNING -> FAILED` outcome. It no longer performs the initial `RECEIVED -> RUNNING` transition. It does not own thread creation, request handling, LINE routing, or execution claiming.

### `app/webhooks/line.py`

Stops invoking `TaskExecutionService` directly for auto-executable tasks. After persistence and ACK, it dispatches only `task.id`. Approval-required tasks transition to `WAITING_APPROVAL`, emit ACTION_REQUIRED, and are not dispatched.

### `app/bootstrap/runtime.py`

Builds the worker and local dispatcher, exposes the dispatcher in runtime dependencies, and provides shutdown cleanup. The FastAPI lifespan closes the dispatcher after `yield`.

## Durable Notification Destination

A task-ID-only worker cannot rely on the webhook's in-memory `LineTextMessage.user_id`. Therefore the LINE source identity required for a later push notification must be persisted when the task is received.

The Task model gains:

```text
source_user_id
```

`TaskService.receive_task()` receives and persists the source user ID for newly created LINE tasks. The worker reloads this value from the database and uses it for DONE/FAILED push notifications.

`source_user_id` is transport/source metadata and must not be stored inside `normalized_intent`, whose purpose remains normalized routing intent.

## Schema Evolution

Task 8B changes the `tasks` schema. The repository currently uses `Base.metadata.create_all()` and does not include a migration framework; `create_all()` creates missing tables but does not add a new column to an existing table.

For Task 8B, schema evolution is handled explicitly rather than silently relying on `create_all()`:

- Fresh databases receive the new column from SQLAlchemy metadata.
- Existing PostgreSQL databases must apply an idempotent SQL migration before the new application version starts using the updated ORM model.
- The repository will include the migration SQL as part of the Task 8B change so deployment is reproducible and versioned.
- Introducing a full Alembic migration framework is outside Task 8B; it can be adopted in a later persistence-hardening milestone.

The migration must preserve existing rows. `source_user_id` is therefore nullable at the database level for backward compatibility, while new LINE-created tasks must always persist a non-empty source user ID before dispatch.

## Task Lifecycle

Task 8B does not add a `QUEUED` task status.

```text
RECEIVED -> RUNNING -> COMPLETED
                    -> FAILED

RECEIVED -> WAITING_APPROVAL
WAITING_APPROVAL -> RUNNING | FAILED
```

The local in-memory executor is not a durable queue. Adding `QUEUED` would imply durability that the implementation does not provide.

## Execution Claim and Idempotency

Background delivery must be treated as at-least-once. The same task ID may be submitted more than once due to webhook retry, dispatcher retry, application behavior, or a future external queue.

A worker may execute OpenAI only after successfully claiming a task whose current status is `RECEIVED`.

`TaskRepository` will expose an execution-claim operation with PostgreSQL row locking semantics (`SELECT ... FOR UPDATE`) inside a transaction:

1. Load and lock the task by `task_id`.
2. If no task exists, return a non-executable result and log it.
3. If status is not `RECEIVED`, return a non-executable result without invoking OpenAI.
4. Transition `RECEIVED -> RUNNING` and commit before the external OpenAI call.
5. Release the row lock when the transaction commits.
6. Pass the now-`RUNNING` task to `TaskExecutionService`, which performs only the terminal transition.

A concurrent worker that later obtains the row sees `RUNNING` or a terminal/non-executable status and skips execution. `TaskExecutionService` must never attempt a second `RUNNING` transition.

The worker skips `RUNNING`, `COMPLETED`, `FAILED`, and `WAITING_APPROVAL` tasks.

## Webhook Flow

For a new auto-executable task:

1. Verify the exact LINE request body signature.
2. Parse the event and route intent.
3. Persist the task, including `source_user_id`.
4. Send the LINE ACK.
5. Call `dispatcher.dispatch(task.id)`.
6. Return the webhook result without waiting for OpenAI execution.

For a new approval-required task:

1. Persist the task.
2. Send ACK.
3. Transition `RECEIVED -> WAITING_APPROVAL`.
4. Send ACTION_REQUIRED.
5. Do not call the dispatcher.

## Duplicate Webhook Recovery

`line_message_id` remains the primary webhook idempotency key.

When a duplicate event resolves to an existing task:

- `RECEIVED` and auto-executable: dispatch the existing `task_id` again so a prior enqueue failure can recover.
- `RUNNING`: do not dispatch.
- `COMPLETED`: do not dispatch.
- `FAILED`: do not dispatch automatically in Task 8B.
- `WAITING_APPROVAL`: do not dispatch.

The execution claim remains the final protection against duplicate OpenAI execution.

## ACK and Dispatch Failure Semantics

### ACK failure

Task durability and execution must not depend on successful ACK delivery. If task persistence succeeds but the ACK call fails, the failure is logged. The auto-executable task remains eligible for dispatch.

### Dispatch failure

`LocalJobDispatcher.dispatch()` raises a dispatcher-specific error when submission cannot be accepted, including dispatch after shutdown. The webhook logs the failure and returns a non-2xx response so LINE can retry. Because the task is already persisted as `RECEIVED`, a duplicate retry can re-dispatch the same task ID safely.

## Worker Error Semantics

### Known AI provider failure

`AIProviderError` produces `FAILED`, persists the provider error details, and triggers a LINE FAILED notification.

### Unexpected execution failure

An unexpected exception after a task is claimed must be caught at the worker/application boundary. If the database is usable, the task is transitioned from `RUNNING` to `FAILED`, concise error details are persisted, and a FAILED notification is attempted. The exception is logged with traceback context.

### Database failure

If the database itself is unavailable, the worker attempts rollback where possible, logs the exception, and must not claim that `FAILED` was persisted when it was not.

### Notification failure

A DONE/FAILED push failure does not change the task's execution result. `COMPLETED` remains `COMPLETED`; `FAILED` remains `FAILED`. Notification retry/outbox behavior is outside Task 8B and the notification error is emitted through structured logging.

## Runtime and Shutdown

`Runtime` owns the dispatcher in addition to the session factory. Application startup constructs the background execution dependencies once. Application shutdown calls dispatcher shutdown from FastAPI lifespan cleanup.

The local executor exposes a configurable maximum worker count:

```text
BACKGROUND_MAX_WORKERS
```

Default: `4`.

The value is explicit because each worker can consume database connections and external API capacity.

## Structured Logging

Task 8B adds structured events for at least:

```text
task.dispatch.requested
task.dispatch.accepted
task.dispatch.failed
task.worker.started
task.worker.skipped
task.worker.completed
task.worker.failed
task.notification.failed
```

Useful fields include `task_id`, `status`, `project_key`, `source_channel`, and `exception_type`. Logs must not contain API keys, access tokens, or complete sensitive request payloads.

## Test Strategy

### Dispatcher tests

- Submits exactly the provided task ID.
- Does not require or transport a SQLAlchemy session or ORM task.
- Observes/logs worker future exceptions.
- Rejects dispatch after shutdown.

### Worker tests

- Creates its own database session.
- Loads a task by ID.
- Always closes the session.
- Executes a `RECEIVED` task.
- Skips `RUNNING`, `COMPLETED`, `FAILED`, and `WAITING_APPROVAL`.
- Persists success and emits DONE to persisted `source_user_id`.
- If legacy data has no `source_user_id`, execution outcome remains authoritative and notification inability is logged rather than rewriting the task result.
- Persists provider failure and emits FAILED.
- Preserves task result when final notification fails.

### Concurrency/idempotency tests

- Duplicate dispatch executes OpenAI at most once.
- Execution claim prevents two workers from claiming the same `RECEIVED` task.
- The locking behavior is verified against PostgreSQL, not inferred only from SQLite tests, because SQLite does not provide equivalent `SELECT ... FOR UPDATE` semantics.
- `TaskExecutionService` is tested with a pre-claimed `RUNNING` task and performs only `RUNNING -> COMPLETED/FAILED`.

### Webhook tests

- Auto-executable task is dispatched after persistence/ACK.
- Dispatcher receives only `task_id`.
- Webhook response does not wait for background OpenAI completion.
- Approval-required task is not dispatched.
- Duplicate auto-executable `RECEIVED` task is re-dispatched.
- Duplicate `RUNNING`, `COMPLETED`, `FAILED`, and `WAITING_APPROVAL` tasks are not dispatched.
- Dispatcher submission failure returns non-2xx and leaves the persisted task recoverable.

### Regression tests

All existing Task 1–8A tests must remain green. Task 8B starts from the recorded baseline of 54 passing tests and 1 warning.

## File Layout

Expected additions and modifications:

```text
app/jobs/__init__.py                 new
app/jobs/dispatcher.py               new
app/jobs/local.py                    new
app/jobs/worker.py                   new
app/tasks/repository.py              modify
app/tasks/executor.py                modify/refine
app/tasks/service.py                 modify
app/persistence/models.py            modify
app/webhooks/line.py                 modify
app/api/dependencies.py              modify
app/bootstrap/runtime.py             modify
app/main.py                          modify
app/config/settings.py               modify
.env.example                         modify
migrations/20260817_add_source_user_id.sql   new

tests/jobs/test_local_dispatcher.py  new
tests/jobs/test_worker.py            new
tests/tasks/test_repository.py       modify
tests/tasks/test_service.py          modify
tests/tasks/test_executor.py         modify as required
tests/webhooks/...                   modify
tests/bootstrap/...                  modify as required
tests/config/...                     modify as required
```

Exact test filenames under existing test packages should follow the repository's current naming conventions when the implementation plan is written.

## Acceptance Criteria

Task 8B is complete when all of the following are true:

- The LINE webhook no longer calls OpenAI execution synchronously.
- The webhook dispatch boundary receives only `task_id`.
- HTTP handling does not wait for OpenAI completion.
- Every background job creates and closes its own SQLAlchemy session.
- No request-scoped session or ORM task crosses into the background executor.
- The worker reloads task state from the database.
- New LINE tasks persist their push-notification source identity.
- `RECEIVED` auto-executable tasks can execute in the background.
- Approval-required / `WAITING_APPROVAL` tasks do not enter the executor.
- Duplicate delivery cannot cause duplicate OpenAI execution.
- `COMPLETED` / `FAILED` are persisted by background execution.
- DONE / FAILED notifications are emitted by the background worker.
- A failed dispatch can recover through a duplicate webhook retry while the task remains `RECEIVED`.
- Local executor shutdown is wired into FastAPI lifespan cleanup.
- Dispatch and worker failures have structured logging.
- The schema change is reproducible for both fresh and existing PostgreSQL databases.
- All pre-Task-8B tests remain green.
- All new Task 8B tests pass.

## Git Milestones

Recommended commit sequence on `feat/background-execution`:

1. `docs: define Task 8B background execution design`
2. `feat: add job dispatcher abstraction`
3. `feat: add local background task worker`
4. `feat: persist task notification source identity`
5. `feat: dispatch webhook tasks asynchronously`
6. `feat: make background execution idempotent`
7. `test: cover background execution lifecycle`
8. `fix: address Task 8B review findings` when review produces code changes

The final pull request should preserve the feature branch and commit history before merge into `main`.
