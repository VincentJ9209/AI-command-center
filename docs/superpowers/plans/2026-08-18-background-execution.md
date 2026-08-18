# Task 8B Background Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move OpenAI execution out of the LINE webhook request lifecycle using a replaceable `JobDispatcher` and a process-local background worker that receives only `task_id`.

**Architecture:** The LINE webhook persists a task, sends ACK, and dispatches only the task ID. `LocalJobDispatcher` submits that ID to `TaskJobWorker`, which creates its own SQLAlchemy session, atomically claims the task, calls `TaskExecutionService`, persists the terminal state, and sends DONE/FAILED using persisted source metadata. The dispatcher can later be replaced by Cloud Tasks or Pub/Sub without rewriting the worker or execution service.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x, PostgreSQL 16, SQLite unit tests, `concurrent.futures.ThreadPoolExecutor`, pytest 8.x.

## Global Constraints

- Work on branch `feat/background-execution`.
- Baseline before Task 8B: `54 passed, 1 warning`.
- Preserve Task 1-8A behavior unless this plan explicitly changes it.
- `JobDispatcher.dispatch()` receives only `task_id: str`.
- Never pass SQLAlchemy `Session`, ORM `Task`, `LineTextMessage`, FastAPI `Request`, or request-scoped dependency objects into background execution.
- Every worker invocation creates and closes its own DB session.
- `WAITING_APPROVAL` / ACTION_REQUIRED tasks are never dispatched by Task 8B.
- Do not add Celery, Redis, RQ, Kafka, RabbitMQ, Cloud Tasks, or Pub/Sub.
- Do not add a `QUEUED` task status.
- New LINE-created tasks persist non-empty `source_user_id`; the DB column remains nullable for legacy rows.
- Existing PostgreSQL schemas must use the versioned SQL migration; do not rely on `Base.metadata.create_all()` to add columns.
- Duplicate delivery must not execute OpenAI more than once for one task.
- Notification failure must not rewrite an already-persisted execution result.
- ACK failure must not prevent dispatch after task persistence.
- Dispatcher submission failure returns non-2xx so LINE can retry; the task remains recoverable as `RECEIVED`.
- Use structured logs without secrets or complete sensitive request payloads.
- Preserve small milestone commits and feature-branch history.

---

## File Map

**Create**
- `app/jobs/__init__.py`
- `app/jobs/dispatcher.py`
- `app/jobs/local.py`
- `app/jobs/worker.py`
- `migrations/20260817_add_source_user_id.sql`
- `tests/jobs/__init__.py`
- `tests/jobs/test_local_dispatcher.py`
- `tests/jobs/test_worker.py`
- `tests/integration/test_task_claim_postgres.py`

**Modify**
- `app/persistence/models.py`
- `app/tasks/repository.py`
- `app/tasks/service.py`
- `app/tasks/executor.py`
- `app/webhooks/line.py`
- `app/api/dependencies.py`
- `app/bootstrap/runtime.py`
- `app/main.py`
- `app/config/settings.py`
- `.env.example`
- `tests/tasks/test_repository.py`
- `tests/tasks/test_service.py`
- `tests/tasks/test_executor.py`
- `tests/webhooks/test_orchestrator.py`
- `tests/api/test_line_webhook.py`
- `tests/bootstrap/test_runtime.py`
- `tests/config/test_settings.py`

---

### Task 1: Add the Dispatcher Abstraction and Local Executor

**Files:**
- Create: `app/jobs/__init__.py`
- Create: `app/jobs/dispatcher.py`
- Create: `app/jobs/local.py`
- Create: `tests/jobs/__init__.py`
- Create: `tests/jobs/test_local_dispatcher.py`

**Interfaces:**
- Produces: `JobDispatcher.dispatch(task_id: str) -> None`
- Produces: `JobDispatchError(RuntimeError)`
- Produces: `LocalJobDispatcher(worker, max_workers: int)`
- Produces: `LocalJobDispatcher.shutdown(wait: bool = True) -> None`
- Consumes: worker object with `run(task_id: str) -> None`

- [ ] **Step 1: Write the failing dispatcher tests**

Create `tests/jobs/test_local_dispatcher.py` with tests equivalent to:

```python
import threading

import pytest

from app.jobs.dispatcher import JobDispatchError
from app.jobs.local import LocalJobDispatcher


class RecordingWorker:
    def __init__(self) -> None:
        self.task_ids: list[str] = []
        self.started = threading.Event()
        self.release = threading.Event()

    def run(self, task_id: str) -> None:
        self.task_ids.append(task_id)
        self.started.set()
        self.release.wait(timeout=2)


def test_dispatch_submits_only_task_id_and_returns_before_worker_finishes() -> None:
    worker = RecordingWorker()
    dispatcher = LocalJobDispatcher(worker, max_workers=1)
    try:
        dispatcher.dispatch("task-123")
        assert worker.started.wait(timeout=1)
        assert worker.task_ids == ["task-123"]
        assert not worker.release.is_set()
    finally:
        worker.release.set()
        dispatcher.shutdown()


def test_dispatch_after_shutdown_raises() -> None:
    dispatcher = LocalJobDispatcher(RecordingWorker(), max_workers=1)
    dispatcher.shutdown()

    with pytest.raises(JobDispatchError):
        dispatcher.dispatch("task-123")
```

Add one test where `worker.run()` raises. A successfully accepted `dispatch()` must not re-raise that asynchronous worker exception; the future callback must observe/log it.

- [ ] **Step 2: Run focused tests to verify RED**

```powershell
pytest tests/jobs/test_local_dispatcher.py -v
```

Expected: import/collection failure because `app.jobs.dispatcher` and `app.jobs.local` do not exist.

- [ ] **Step 3: Implement the dispatcher contract**

Create `app/jobs/dispatcher.py`:

```python
from typing import Protocol


class JobDispatchError(RuntimeError):
    pass


class JobDispatcher(Protocol):
    def dispatch(self, task_id: str) -> None:
        ...
```

Create `app/jobs/local.py` around `ThreadPoolExecutor`.

Required behavior:
- `dispatch()` logs `task.dispatch.requested`;
- `executor.submit(worker.run, task_id)` is the only payload handoff;
- immediate `RuntimeError` from submission becomes `JobDispatchError` and logs `task.dispatch.failed`;
- accepted submission logs `task.dispatch.accepted`;
- a done callback calls `future.exception()` and logs asynchronous failure with `task_id`;
- `shutdown(wait=True)` delegates to the executor.

- [ ] **Step 4: Run focused tests to verify GREEN**

```powershell
pytest tests/jobs/test_local_dispatcher.py -v
```

Expected: PASS.

- [ ] **Step 5: Run regression suite**

```powershell
pytest -q
```

Expected: prior tests plus new dispatcher tests pass; the known Starlette warning is acceptable.

- [ ] **Step 6: Commit**

```powershell
git add app/jobs tests/jobs
git commit -m "feat: add job dispatcher abstraction"
```

---

### Task 2: Persist the Background Notification Source Identity

**Files:**
- Create: `migrations/20260817_add_source_user_id.sql`
- Modify: `app/persistence/models.py`
- Modify: `app/tasks/repository.py`
- Modify: `app/tasks/service.py`
- Modify: `tests/tasks/test_repository.py`
- Modify: `tests/tasks/test_service.py`

**Interfaces:**
- Produces: `Task.source_user_id: str | None`
- Changes: `TaskRepository.create(..., source_user_id: str | None = None)`
- Changes: `TaskService.receive_task(..., source_user_id: str | None = None)`
- Produces: `TaskRepository.get_by_id(task_id: str) -> Task | None`

- [ ] **Step 1: Add failing persistence tests**

Add tests asserting a new task persists `source_user_id="user-1"` and can be reloaded by task ID.

Representative assertion:

```python
result = service.receive_task(
    line_message_id="source-user-test",
    project_key="GENERAL",
    request_text="summarize",
    source_user_id="user-1",
)

assert result.task.source_user_id == "user-1"
assert TaskRepository(session).get_by_id(result.task.id).id == result.task.id
```

Retain the existing duplicate `line_message_id` behavior and assert a duplicate returns the original task rather than creating a second row.

- [ ] **Step 2: Run focused tests to verify RED**

```powershell
pytest tests/tasks/test_repository.py tests/tasks/test_service.py -v
```

Expected: FAIL because the model/service/repository do not yet support `source_user_id`.

- [ ] **Step 3: Add model/repository/service support**

In `Task`:

```python
source_user_id: Mapped[str | None] = mapped_column(
    String(128),
    nullable=True,
)
```

Extend repository/service call signatures to accept and persist the value.

Add:

```python
def get_by_id(self, task_id: str) -> Task | None:
    return self.session.get(Task, task_id)
```

Do not use `normalized_intent` for transport identity.

- [ ] **Step 4: Add the idempotent PostgreSQL migration**

Create `migrations/20260817_add_source_user_id.sql`:

```sql
ALTER TABLE tasks
ADD COLUMN IF NOT EXISTS source_user_id VARCHAR(128);
```

Do not make the DB column `NOT NULL` in Task 8B because old rows may exist without it.

- [ ] **Step 5: Run focused and full tests**

```powershell
pytest tests/tasks/test_repository.py tests/tasks/test_service.py -v
pytest -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add app/persistence/models.py app/tasks/repository.py app/tasks/service.py tests/tasks/test_repository.py tests/tasks/test_service.py migrations/20260817_add_source_user_id.sql
git commit -m "feat: persist task notification source identity"
```

---

### Task 3: Add Atomic Execution Claim and Refine the Execution Service

**Files:**
- Modify: `app/tasks/repository.py`
- Modify: `app/tasks/executor.py`
- Modify: `tests/tasks/test_repository.py`
- Modify: `tests/tasks/test_executor.py`

**Interfaces:**
- Produces: `TaskRepository.claim_for_execution(task_id: str) -> Task | None`
- Changes: `TaskExecutionService.execute(task: Task)` requires `task.status == RUNNING`
- Execution service performs only `RUNNING -> COMPLETED` or `RUNNING -> FAILED`

- [ ] **Step 1: Write failing execution-claim tests**

Cover:
- `RECEIVED` task becomes `RUNNING`;
- missing ID returns `None`;
- `RUNNING`, `COMPLETED`, `FAILED`, `WAITING_APPROVAL` return `None`;
- one `RECEIVED -> RUNNING` `TaskEvent` is persisted.

Representative test:

```python
claimed = repository.claim_for_execution(task.id)

assert claimed is not None
assert claimed.status == TaskStatus.RUNNING.value
assert session.get(Task, task.id).status == TaskStatus.RUNNING.value
```

- [ ] **Step 2: Rewrite executor tests for the pre-claimed contract**

Change executor test setup so a task is created and then claimed before passing it to `TaskExecutionService`.

Add a precondition test:

```python
with pytest.raises(ValueError, match="RUNNING"):
    TaskExecutionService(session, SuccessfulProvider()).execute(received_task)
```

Expected lifecycle:

```text
RECEIVED -> RUNNING  # claim
RUNNING -> COMPLETED # execution service
```

- [ ] **Step 3: Run focused tests to verify RED**

```powershell
pytest tests/tasks/test_repository.py tests/tasks/test_executor.py -v
```

- [ ] **Step 4: Implement `claim_for_execution()`**

Use row locking:

```python
statement = (
    select(Task)
    .where(Task.id == task_id)
    .with_for_update()
)
task = self.session.scalar(statement)
```

Rules:
1. missing task -> end transaction and return `None`;
2. status other than `RECEIVED` -> end transaction and return `None`;
3. `RECEIVED` -> `transition(task, TaskStatus.RUNNING)`;
4. commit before returning, so the row lock is released before OpenAI is called.

- [ ] **Step 5: Refine `TaskExecutionService.execute()`**

Remove its initial `RECEIVED -> RUNNING` transition.

At entry:

```python
if TaskStatus(task.status) is not TaskStatus.RUNNING:
    raise ValueError("Task must be RUNNING before execution")
```

Keep `AIProviderError` -> FAILED and successful execution -> COMPLETED, each with one commit.

- [ ] **Step 6: Run focused and full tests**

```powershell
pytest tests/tasks/test_repository.py tests/tasks/test_executor.py -v
pytest -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add app/tasks/repository.py app/tasks/executor.py tests/tasks/test_repository.py tests/tasks/test_executor.py
git commit -m "feat: make background execution idempotent"
```

---

### Task 4: Implement `TaskJobWorker`

**Files:**
- Create: `app/jobs/worker.py`
- Create: `tests/jobs/test_worker.py`

**Interfaces:**
- Produces: `TaskJobWorker(session_factory, provider, notification_service)`
- Produces: `TaskJobWorker.run(task_id: str) -> None`
- Consumes: `TaskRepository.claim_for_execution()`
- Consumes: `TaskExecutionService.execute()`
- Consumes: persisted `Task.source_user_id`

- [ ] **Step 1: Write failing worker ownership/success tests**

Prove:
- session factory is called inside `run()`;
- worker accepts only `task_id`;
- session is closed in `finally`;
- RECEIVED task becomes COMPLETED;
- provider executes once;
- `[DONE]` push goes to persisted `source_user_id`.

- [ ] **Step 2: Write failing skip tests**

Parametrize `RUNNING`, `COMPLETED`, `FAILED`, and `WAITING_APPROVAL`. Assert:
- provider calls = 0;
- push calls = 0;
- state is unchanged;
- worker logs `task.worker.skipped`.

- [ ] **Step 3: Write failing failure/notification tests**

Cover:
- `AIProviderError` -> FAILED + `[FAILED]` push;
- unexpected exception after claim -> best-effort `RUNNING -> FAILED`, error persisted, `task.worker.failed` logged;
- legacy task with `source_user_id is None` -> execution result remains authoritative and notification is skipped/logged;
- push failure after COMPLETED -> remains COMPLETED;
- push failure after FAILED -> remains FAILED.

- [ ] **Step 4: Run worker tests to verify RED**

```powershell
pytest tests/jobs/test_worker.py -v
```

- [ ] **Step 5: Implement worker orchestration**

Required shape:

```python
class TaskJobWorker:
    def __init__(
        self,
        session_factory,
        provider,
        notification_service,
    ) -> None:
        self.session_factory = session_factory
        self.provider = provider
        self.notification_service = notification_service

    def run(self, task_id: str) -> None:
        session = self.session_factory()
        task = None
        try:
            repository = TaskRepository(session)
            task = repository.claim_for_execution(task_id)
            if task is None:
                return

            outcome = TaskExecutionService(
                session,
                self.provider,
            ).execute(task)

            self._send_terminal_notification(task, outcome)
        except Exception as exc:
            session.rollback()
            self._persist_unexpected_failure_if_possible(
                session,
                task_id,
                exc,
            )
        finally:
            session.close()
```

Implementation requirements:
- log `task.worker.started`;
- do not put thread/executor code here;
- on unexpected exception, rollback first, reload by ID, transition to FAILED only if current state is RUNNING, and commit best-effort;
- if DB recovery also fails, log with traceback and do not claim FAILED was persisted;
- notification sending has its own exception boundary and logs `task.notification.failed`;
- log `task.worker.completed` for terminal completion.

- [ ] **Step 6: Run worker and full tests**

```powershell
pytest tests/jobs/test_worker.py -v
pytest -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add app/jobs/worker.py tests/jobs/test_worker.py
git commit -m "feat: add local background task worker"
```

---

### Task 5: Replace Synchronous LINE Execution with Dispatch

**Files:**
- Modify: `app/webhooks/line.py`
- Modify: `app/api/dependencies.py`
- Modify: `tests/webhooks/test_orchestrator.py`
- Modify: `tests/api/test_line_webhook.py`

**Interfaces:**
- Changes: `LineWebhookOrchestrator(..., dispatcher: JobDispatcher)`
- Changes: `LineWebhookDependencies` gains `dispatcher: JobDispatcher`
- Webhook persists `source_user_id=message.user_id`
- Auto-executable tasks call only `dispatcher.dispatch(task.id)`

- [ ] **Step 1: Replace synchronous success tests with dispatch tests**

Use:

```python
class RecordingDispatcher:
    def __init__(self) -> None:
        self.task_ids: list[str] = []

    def dispatch(self, task_id: str) -> None:
        self.task_ids.append(task_id)
```

For a new auto-executable message assert:
- task exists as `RECEIVED` when orchestrator returns;
- `task.source_user_id == "user-1"`;
- one ACK;
- dispatcher receives only `[task.id]`;
- zero DONE/FAILED pushes during request processing;
- provider is not called by the orchestrator.

- [ ] **Step 2: Add approval exclusion tests**

For an approval-required message assert:
- `WAITING_APPROVAL`;
- ACK + ACTION_REQUIRED;
- zero dispatcher calls.

- [ ] **Step 3: Add duplicate recovery tests**

Replay the same `line_message_id` against persisted tasks:
- `RECEIVED` + `requires_approval=False` -> re-dispatch same task ID;
- `RUNNING`, `COMPLETED`, `FAILED`, `WAITING_APPROVAL` -> no dispatch;
- no duplicate Task row.

Use persisted `normalized_intent["requires_approval"]` to determine whether a duplicate RECEIVED task is auto-executable.

- [ ] **Step 4: Add ACK-failure semantics test**

Use a notification client whose reply/ACK raises.

Assert:
- task remains persisted;
- auto-executable task is still handed to dispatcher;
- ACK failure is logged;
- ACK failure itself does not mark task FAILED.

Implement ACK as a best-effort side effect after durable persistence.

- [ ] **Step 5: Add dispatch-failure API test**

Use a dispatcher that raises `JobDispatchError`.

Assert:
- endpoint returns HTTP 503;
- task remains `RECEIVED`;
- a subsequent duplicate request with a working dispatcher can re-dispatch the same task ID.

- [ ] **Step 6: Run webhook/API tests to verify RED**

```powershell
pytest tests/webhooks/test_orchestrator.py tests/api/test_line_webhook.py -v
```

- [ ] **Step 7: Implement the dispatch flow**

Changes:
- remove direct `TaskExecutionService` construction/call from `LineWebhookOrchestrator`;
- persist `source_user_id=message.user_id`;
- send ACK inside a logging exception boundary;
- approval-required path remains `WAITING_APPROVAL` + ACTION_REQUIRED and returns without dispatch;
- new auto-executable path calls `dispatcher.dispatch(task.id)`;
- duplicate RECEIVED auto-executable path re-dispatches;
- other duplicate states skip;
- API boundary maps `JobDispatchError` to HTTP 503.

Do not send DONE/FAILED from the webhook layer.

- [ ] **Step 8: Run focused and full tests**

```powershell
pytest tests/webhooks/test_orchestrator.py tests/api/test_line_webhook.py -v
pytest -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```powershell
git add app/webhooks/line.py app/api/dependencies.py tests/webhooks/test_orchestrator.py tests/api/test_line_webhook.py
git commit -m "feat: dispatch webhook tasks asynchronously"
```

---

### Task 6: Wire Background Execution into Runtime and Lifespan

**Files:**
- Modify: `app/config/settings.py`
- Modify: `.env.example`
- Modify: `app/bootstrap/runtime.py`
- Modify: `app/main.py`
- Modify: `tests/config/test_settings.py`
- Modify: `tests/bootstrap/test_runtime.py`

**Interfaces:**
- Produces: `Settings.background_max_workers: int = 4`
- Runtime owns `LocalJobDispatcher`
- Runtime exposes `close()`
- FastAPI lifespan invokes runtime cleanup after `yield`

- [ ] **Step 1: Add failing settings tests**

Add:
```python
assert Settings.from_env().background_max_workers == 4
```

Override:
```python
monkeypatch.setenv("BACKGROUND_MAX_WORKERS", "2")
assert Settings.from_env().background_max_workers == 2
```

Also assert `"0"`, negative values, and non-integers raise `SettingsError` mentioning `BACKGROUND_MAX_WORKERS`.

- [ ] **Step 2: Add failing runtime wiring tests**

Monkeypatch `TaskJobWorker` and `LocalJobDispatcher`.

Assert:
- worker gets `session_factory`, provider, notification service;
- dispatcher gets that worker and configured worker count;
- webhook dependencies get the same dispatcher;
- `Runtime.close()` calls dispatcher shutdown.

- [ ] **Step 3: Run focused tests to verify RED**

```powershell
pytest tests/config/test_settings.py tests/bootstrap/test_runtime.py -v
```

- [ ] **Step 4: Implement settings/runtime wiring**

Add:

```python
background_max_workers: int = 4
```

Parse `BACKGROUND_MAX_WORKERS`, default `4`, reject values `< 1`.

Construct runtime in this order:

```text
engine/session_factory
provider
LINE client/notification service
TaskJobWorker
LocalJobDispatcher
webhook dependencies
Runtime
```

`Runtime.close()` delegates to `dispatcher.shutdown()`.

- [ ] **Step 5: Wire FastAPI lifespan cleanup**

Use:

```python
runtime = configure_runtime(settings)
app.state.runtime = runtime

try:
    yield
finally:
    runtime.close()
```

Do not alter `/health` or `/ready` semantics.

- [ ] **Step 6: Update `.env.example`**

Add:

```dotenv
BACKGROUND_MAX_WORKERS=4
```

- [ ] **Step 7: Run focused and full tests**

```powershell
pytest tests/config/test_settings.py tests/bootstrap/test_runtime.py tests/test_health.py tests/test_readiness.py -v
pytest -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```powershell
git add app/config/settings.py .env.example app/bootstrap/runtime.py app/main.py tests/config/test_settings.py tests/bootstrap/test_runtime.py
git commit -m "feat: wire background execution runtime"
```

---

### Task 7: Verify PostgreSQL Row-Locking Concurrency

**Files:**
- Create: `tests/integration/test_task_claim_postgres.py`

**Interfaces:**
- Validates: `TaskRepository.claim_for_execution()` allows at most one successful claim on PostgreSQL.

- [ ] **Step 1: Add PostgreSQL-only integration test**

Read `TEST_POSTGRES_DATABASE_URL`. If absent, skip with an explicit reason.

Test setup:
- create schema with `Base.metadata.create_all()`;
- insert one RECEIVED task;
- create two independent sessions;
- synchronize two threads with `threading.Barrier`;
- both call `claim_for_execution(task_id)`;
- assert exactly one returns a Task and exactly one returns `None`;
- final task status is RUNNING;
- exactly one `RECEIVED -> RUNNING` event exists.

Do not treat SQLite as proof of `SELECT ... FOR UPDATE` behavior.

- [ ] **Step 2: Start ephemeral PostgreSQL**

PowerShell:

```powershell
docker run --rm -d --name aicc-task8b-postgres `
  -e POSTGRES_DB=aicc_test `
  -e POSTGRES_USER=postgres `
  -e POSTGRES_PASSWORD=postgres `
  -p 55432:5432 postgres:16-alpine
```

Readiness:

```powershell
docker exec aicc-task8b-postgres pg_isready -U postgres -d aicc_test
```

- [ ] **Step 3: Run locking test**

```powershell
$env:TEST_POSTGRES_DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:55432/aicc_test"
pytest tests/integration/test_task_claim_postgres.py -v
```

Expected: PASS with exactly one successful claim.

- [ ] **Step 4: Clean up**

```powershell
docker stop aicc-task8b-postgres
Remove-Item Env:TEST_POSTGRES_DATABASE_URL
```

- [ ] **Step 5: Run ordinary suite without PostgreSQL env**

```powershell
pytest -q
```

Expected: PASS; PostgreSQL-only test may be SKIPPED.

- [ ] **Step 6: Commit**

```powershell
git add tests/integration/test_task_claim_postgres.py
git commit -m "test: verify background execution locking"
```

---

### Task 8: Apply Migration and Run the Task 8B Acceptance Gate

**Files:**
- Review all Task 8B changes.
- Modify only files required by review findings.

**Interfaces:**
- Validates complete Task 8B behavior and branch quality.

- [ ] **Step 1: Apply migration to existing development PostgreSQL**

```powershell
docker compose up -d db
Get-Content migrations/20260817_add_source_user_id.sql | docker compose exec -T db psql -U postgres -d ai_command_center
```

Run the same command twice. Both runs must succeed.

- [ ] **Step 2: Verify schema**

```powershell
docker compose exec -T db psql -U postgres -d ai_command_center -c "\d tasks"
```

Expected: `source_user_id character varying(128)` exists.

- [ ] **Step 3: Run full automated suite**

```powershell
pytest -q
```

Expected: all tests pass. Only the previously known Starlette deprecation warning is acceptable unless deliberately resolved in a separate change.

- [ ] **Step 4: Run targeted Task 8B tests**

```powershell
pytest tests/jobs tests/tasks tests/webhooks tests/api tests/bootstrap tests/config -v
```

Verify from tests/output:
- webhook no longer executes OpenAI synchronously;
- dispatcher payload is task ID only;
- worker owns DB session;
- WAITING_APPROVAL is never dispatched;
- duplicate RECEIVED can recover via re-dispatch;
- duplicate execution is prevented by claim;
- DONE/FAILED comes from worker using persisted source identity;
- notification failure does not rewrite task result;
- runtime shutdown closes local executor.

- [ ] **Step 5: Inspect branch state/history**

```powershell
git status
git log --oneline --decorate -12
```

Expected:
- branch `feat/background-execution`;
- clean working tree;
- design commit `1be06a4` plus distinct implementation milestones.

- [ ] **Step 6: Review diff against main**

```powershell
git diff --check main...HEAD
git diff --stat main...HEAD
git diff main...HEAD
```

Review specifically for:
- secrets;
- Session/ORM objects crossing dispatcher boundary;
- provider execution still present in webhook request path;
- unrelated refactors;
- notification errors corrupting task execution state;
- missing structured logging events.

`git diff --check` must produce no whitespace errors.

- [ ] **Step 7: Fix review findings through TDD**

For each finding:
1. add/adjust a failing regression test;
2. run it and verify failure;
3. apply the smallest fix;
4. rerun focused test;
5. rerun `pytest -q`.

If changes were required:

```powershell
git add <changed-files>
git commit -m "fix: address Task 8B review findings"
```

If no findings exist, do not create an empty commit.

- [ ] **Step 8: Stop before merge**

Do not merge yet. Preserve `feat/background-execution` and its commit history. Next gate is review/PR preparation, then merge through VS Code/Git CLI while GitHub service remains unstable.

---

## Final Acceptance Checklist

- [ ] LINE webhook no longer calls OpenAI synchronously.
- [ ] Webhook dispatches only `task_id`.
- [ ] HTTP request handling does not wait for background OpenAI completion.
- [ ] Background worker creates/closes its own SQLAlchemy Session.
- [ ] ORM Task/request Session never crosses dispatcher boundary.
- [ ] Worker reloads and claims task by ID.
- [ ] New LINE tasks persist `source_user_id`.
- [ ] Existing PostgreSQL DB receives the versioned schema migration.
- [ ] RECEIVED auto-executable tasks run in background.
- [ ] WAITING_APPROVAL/ACTION_REQUIRED tasks do not enter executor.
- [ ] Duplicate delivery cannot produce duplicate OpenAI execution.
- [ ] Duplicate RECEIVED webhook can recover from enqueue failure.
- [ ] ACK failure does not prevent dispatch after persistence.
- [ ] Dispatch failure leaves a recoverable RECEIVED task and returns non-2xx.
- [ ] Worker persists COMPLETED/FAILED.
- [ ] Worker emits DONE/FAILED using persisted source identity.
- [ ] Notification failure preserves execution result.
- [ ] Runtime shutdown closes local executor.
- [ ] Dispatch/worker structured logs exist and do not expose secrets.
- [ ] PostgreSQL locking is verified against PostgreSQL.
- [ ] All Task 1-8A regression tests remain green.
- [ ] All Task 8B tests pass.
- [ ] `git diff --check main...HEAD` is clean.
- [ ] Feature branch is preserved and remains unmerged until review gate.
