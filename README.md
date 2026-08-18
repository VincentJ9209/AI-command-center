# AI Command Center

以 LINE 作為入口的個人 AI 任務指揮中心，同時作為 AI Application / Backend / Data Engineering 作品集專案。

## 目前已完成功能

- FastAPI API 服務
- `/health` 健康檢查
- `/ready` 資料庫就緒檢查
- LINE Webhook HMAC-SHA256 簽章驗證
- LINE 文字訊息解析
- AI Skill Market Intelligence 任務路由
- 高風險操作人工審核機制
- SQLAlchemy 任務持久化與狀態生命週期
- OpenAI Responses API 任務執行
- LINE ACK / DONE / FAILED / ACTION_REQUIRED 通知
- Webhook 端到端任務流程
- PostgreSQL Production Runtime
- Docker / Docker Compose
- 背景任務執行架構
- Worker 獨立 Database Session
- Task Atomic Claim，避免重複 Worker 執行
- LINE Webhook 快速回應，不等待 AI 任務完成
- 重複 Webhook Delivery 防護
- Versioned SQL Migration
- `source_user_id` 任務來源識別

## 系統流程

LINE 收到訊息後：

```text
LINE
  ↓
Webhook 驗證
  ↓
解析訊息
  ↓
建立 Task
  ↓
回覆 ACK
  ↓
JobDispatcher
  ↓
Background Worker
  ↓
OpenAI 執行
  ↓
更新 Task 狀態
  ↓
LINE DONE / FAILED

```

Webhook 不需要等待 AI 工作完成，因此可以快速回覆 LINE。

## Background Execution

目前 Local Runtime 使用 `ThreadPoolExecutor` 執行背景工作。

背景 Worker 數量由以下環境變數控制：

```env
BACKGROUND_MAX_WORKERS=4
```

預設值為 `4`。

背景執行流程：

```text
Webhook
  ↓
建立 Task
  ↓
ACK
  ↓
JobDispatcher.dispatch(task_id)
  ↓
Background Worker
  ↓
取得並 Claim Task
  ↓
RECEIVED → RUNNING
  ↓
執行 AI 任務
  ↓
RUNNING → COMPLETED / FAILED
  ↓
LINE DONE / FAILED
```

Dispatcher 只傳遞 `task_id`。

Worker 會自行建立 Database Session，避免 Webhook Request Session 被背景執行緒重複使用。

這個邊界設計讓未來可以將 Local Dispatcher 替換成 Cloud Tasks、Pub/Sub 或其他 Durable Queue，而不需要重寫核心 Task Worker。

## 本機開發

先由 `.env.example` 建立本機 `.env`：

```powershell
Copy-Item .env.example .env
```

安裝專案與開發依賴：

```powershell
python -m pip install -e ".[dev]"
```

一般測試：

```powershell
pytest -q
```

`.env` 包含本機憑證與 API Key，不可提交至 Git。

## PostgreSQL Integration Test

PostgreSQL Integration Test 使用專用資料庫：

```text
ai_command_center_test
```

啟動測試資料庫：

```powershell
docker compose -f docker-compose.test.yml up -d
```

設定：

```powershell
$env:POSTGRES_TEST_DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:55432/ai_command_center_test"
```

執行：

```powershell
pytest -q
```

Integration Test 具有資料庫安全防護：

- 未設定 `POSTGRES_TEST_DATABASE_URL` 時自動 Skip
- 必須使用 PostgreSQL
- Database Name 必須為 `ai_command_center_test`
- 如果指向其他資料庫，測試會拒絕執行 destructive operation

使用完成後：

```powershell
docker compose -f docker-compose.test.yml down
```

不要使用 `-v`，除非確定要刪除相關 Volume。

## Database Migration

目前使用 Versioned SQL Migration。

本次 Schema Migration：

```text
migrations/20260817_add_source_user_id.sql
```

內容使用：

```sql
ADD COLUMN IF NOT EXISTS
```

因此可以安全重複執行。

### 全新資料庫

如果 PostgreSQL Database 是全新建立，可以直接：

```powershell
docker compose up -d --build
```

Application 會依目前 SQLAlchemy Model 建立 Schema。

### 既有資料庫

如果資料庫是在 `source_user_id` 加入之前建立，必須先 Migration，再啟動新版 Application。

先啟動 Database：

```powershell
docker compose up -d db
```

執行 Migration：

```powershell
Get-Content migrations/20260817_add_source_user_id.sql |
    docker compose exec -T db psql `
        -v ON_ERROR_STOP=1 `
        -U postgres `
        -d ai_command_center
```

Migration 成功後才啟動新版 Application：

```powershell
docker compose up -d --build app
```

新版 Application 不應在舊 Database Migration 尚未成功時直接啟動。

## Docker

啟動：

```powershell
docker compose up -d --build
```

查看狀態：

```powershell
docker compose ps
```

查看 Application Log：

```powershell
docker compose logs app --tail 50
```

主要 Endpoint：

```text
GET  /health
GET  /ready
POST /webhooks/line
```

停止：

```powershell
docker compose down
```

## 下一階段

目前 Local Background Execution 已完成。

下一階段將評估把 `LocalJobDispatcher` 替換成具備 Durable Delivery 能力的外部 Queue，例如：

- Google Cloud Tasks
- Google Pub/Sub
- Redis Queue
- RabbitMQ

現有：

```text
JobDispatcher
    ↓
TaskJobWorker
```

介面會保留，因此更換 Queue Backend 時不需要重寫核心 AI 任務執行邏輯。

後續 Production 能力可再加入：

- Retry Policy
- Dead Letter Queue
- Queue Observability
- Horizontal Worker Scaling
- Production Deployment