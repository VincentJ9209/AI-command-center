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