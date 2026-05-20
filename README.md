# 輿情分析系統

本專案是一個輿情分析系統，用於收集文章資料、儲存到 PostgreSQL，並透過 FastAPI 後端與 Vue 前端進行展示。

Repository：  
https://github.com/xujiaquan05/114

---

## 1. 從 GitHub 下載專案

打開 PowerShell 或 Terminal，進入你想放專案的資料夾，例如 Desktop：

```bash
cd Desktop
```

下載專案：

```bash
git clone https://github.com/xujiaquan05/114.git
```

進入專案資料夾：

```bash
cd 114
```

---

## 2. 專案結構

```text
114/
├── backend/
│   ├── app/
│   ├── requirements.txt
│   └── .env
│
├── frontend/
│   ├── src/
│   ├── package.json
│   └── vite.config.js
│
├── database/
│   └── init.sql
│
└── README.md
```

---

## 3. 後端 Backend 安裝

進入後端資料夾：

```bash
cd backend
```

建立 Python 虛擬環境：

```bash
python -m venv venv
```

啟動虛擬環境。

Windows PowerShell：

```bash
.\venv\Scripts\Activate.ps1
```

Windows CMD：

```bash
venv\Scripts\activate.bat
```

macOS / Linux：

```bash
source venv/bin/activate
```

安裝 Python 套件：

```bash
pip install -r requirements.txt
```

---

## 4. 建立 `.env` 環境變數檔案

在 `backend` 資料夾裡建立一個檔案：

```text
.env
```

內容範例：

```env
DATABASE_URL=postgresql://postgres:your_password@localhost:5432/medical_beauty_db
GOOGLE_API_KEY=your_google_api_key
APP_NAME=Medical Beauty Public Opinion System
APP_ENV=development
```

請把：

```text
your_password
```

改成你自己的 PostgreSQL 密碼。

如果你的 PostgreSQL 不是使用預設 port `5432`，例如你使用的是 `7042`，請改成：

```env
DATABASE_URL=postgresql://postgres:your_password@localhost:7042/medical_beauty_db
```

---

## 5. 建立 PostgreSQL 資料庫

登入 PostgreSQL：

```bash
psql -U postgres
```

建立資料庫：

```sql
CREATE DATABASE medical_beauty_db;
```

離開 PostgreSQL：

```sql
\q
```

執行資料表初始化 SQL：

```bash
psql -U postgres -d medical_beauty_db -f ../database/init.sql
```

---

## 6. 啟動後端

確認目前在 `backend` 資料夾，並且已經啟動 Python 虛擬環境。

執行：

```bash
python -m uvicorn app.main:app --reload --port 8000
```

打開瀏覽器：

```text
http://localhost:8000
```

查看 API 文件：

```text
http://localhost:8000/docs
```

查看系統健康狀態：

```text
http://localhost:8000/health
```

如果成功，應該會看到：

```json
{
  "api": "ok",
  "database": "connected"
}
```

---

## 7. 前端 Frontend 安裝

另外開一個新的 Terminal，進入前端資料夾：

```bash
cd frontend
```

安裝前端套件：

```bash
npm install
```

啟動前端：

```bash
npm run dev
```

啟動後，Vite 會顯示前端網址，通常是：

```text
http://localhost:5173
```

如果想指定使用 port `3000`：

```bash
npm run dev -- --port 3000
```

然後打開：

```text
http://localhost:3000
```

---

## 8. 從 GitHub 更新最新程式碼

如果已經 clone 過專案，之後想更新到 GitHub 上最新版本：

```bash
git pull origin main
```

---

## 9. 將本機修改推送到 GitHub

查看目前修改狀態：

```bash
git status
```

加入所有修改：

```bash
git add .
```

建立 commit：

```bash
git commit -m "Update project"
```

推送到 GitHub：

```bash
git push origin main
```

---

## 10. 不要上傳到 GitHub 的檔案

以下檔案或資料夾不應該上傳到 GitHub：

```text
backend/venv/
frontend/node_modules/
backend/.env
frontend/.env
```

原因：

| 檔案 / 資料夾 | 原因 |
|---|---|
| `backend/venv/` | Python 虛擬環境很大，而且每台電腦可以自己建立 |
| `frontend/node_modules/` | 前端套件很大，可以用 `npm install` 重新安裝 |
| `.env` | 裡面可能有資料庫密碼或 API Key，不應公開 |

`.gitignore` 建議內容：

```gitignore
# Python
backend/venv/
__pycache__/
*.pyc

# Environment variables
.env
backend/.env
frontend/.env

# Node
frontend/node_modules/
frontend/dist/

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db
```

---

## 11. 常見錯誤處理

### 錯誤一：`uvicorn is not recognized`

代表系統找不到 `uvicorn` 指令。

建議使用：

```bash
python -m uvicorn app.main:app --reload --port 8000
```

如果還是不行，重新安裝：

```bash
pip install uvicorn fastapi
```

---

### 錯誤二：`password authentication failed for user "postgres"`

代表 PostgreSQL 密碼錯誤。

請檢查 `backend/.env` 裡的這一行：

```env
DATABASE_URL=postgresql://postgres:your_password@localhost:5432/medical_beauty_db
```

把 `your_password` 改成你真正的 PostgreSQL 密碼。

如果你的 PostgreSQL port 是 `7042`，要改成：

```env
DATABASE_URL=postgresql://postgres:your_password@localhost:7042/medical_beauty_db
```

修改 `.env` 後，請重新啟動後端。

---

### 錯誤三：前端跑在 `5173`，不是 `3000`

這不是錯誤。Vite 預設使用 port `5173`。

如果想指定 port `3000`：

```bash
npm run dev -- --port 3000
```

---

### 錯誤四：`git push` 被 rejected

通常是 GitHub 上已經有檔案，本機沒有同步。

先拉取遠端內容：

```bash
git pull origin main --allow-unrelated-histories
```

如果沒有 conflict，再推送：

```bash
git push origin main
```

如果發生 `.gitignore` conflict，可以保留本機版本：

```bash
git checkout --ours .gitignore
git add .gitignore
git commit -m "Merge remote repository"
git push origin main
```

---

## 12. Phase 1 完成檢查

後端 API 文件：

```text
http://localhost:8000/docs
```

前端畫面：

```text
http://localhost:5173
```

系統健康檢查：

```text
http://localhost:8000/health
```

成功結果：

```json
{
  "api": "ok",
  "database": "connected"
}
```

如果以上三項都能正常顯示，代表 Phase 1 已完成。

---

## 13. 開發時常用指令整理

### 啟動後端

```bash
cd backend
.\venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload --port 8000
```

### 啟動前端

```bash
cd frontend
npm run dev
```

### 更新 GitHub 程式碼到本機

```bash
git pull origin main
```

### 推送本機程式碼到 GitHub

```bash
git add .
git commit -m "Update project"
git push origin main
```

---

## Phase 6-8 demo checklist

Backend endpoints:

```text
GET  /api/dashboard/full
POST /api/crawler/ptt
WS   /ws/dashboard
POST /api/qa/ask
GET  /api/export/articles.xlsx
```

Frontend pages:

```text
Dashboard: http://localhost:5173/
AI Q&A:    http://localhost:5173/qa
History:   http://localhost:5173/history
```

Demo flow:

```text
1. Open Dashboard and search a keyword.
2. Click Crawl and watch the realtime WebSocket progress panel.
3. Click Excel to download the current article query result.
4. Open AI Q&A and ask: 最近玻尿酸有哪些負評？
5. Check that the answer includes key points, marketing action, and clickable sources.
```

Quick API test:

```bash
curl -X POST http://localhost:8000/api/qa/ask ^
  -H "Content-Type: application/json" ^
  -d "{\"question\":\"最近玻尿酸有哪些負評？\"}"
```
