# MeBOD 後端的開機啟動腳本（供 Windows 工作排程器呼叫）。
#
# 為什麼不是 Windows 服務？
# Dcard、Mobile01 與 Threads 的爬蟲以 headless=False 開真實瀏覽器視窗
# （這三個站台都會擋無頭瀏覽器）。Windows 服務跑在 Session 0，沒有桌面，
# Playwright 無法開視窗，這三個平台會整批失敗。
# 因此改用「登入時啟動」的排程工作，讓後端待在有桌面的互動工作階段裡。
#
# 註冊方式見 scripts/install_autostart.ps1；移除方式見同一個檔案的說明。

$ErrorActionPreference = "Stop"

# 腳本在 backend/scripts 底下，專案的 backend 目錄是它的上一層。
$BackendDir = Split-Path -Parent $PSScriptRoot
Set-Location $BackendDir

$Python = Join-Path $BackendDir "venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    throw "找不到虛擬環境：$Python。請先建立 venv 並安裝 requirements.txt。"
}

# 日誌按日期分檔，方便事後查「某天後端有沒有起來」。
$LogDir = Join-Path $BackendDir "logs"
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
$LogFile = Join-Path $LogDir ("server-{0}.log" -f (Get-Date -Format "yyyy-MM-dd"))

"[{0}] 啟動後端（PID {1}）" -f (Get-Date -Format "HH:mm:ss"), $PID | Out-File -FilePath $LogFile -Append -Encoding utf8

# uvicorn 把執行日誌寫到 stderr。在 Windows PowerShell 5.1 裡，對原生程式使用
# 2>&1 會把每一行 stderr 包成 NativeCommandError；配上上面的
# $ErrorActionPreference = "Stop"，伺服器才剛印出第一行啟動訊息，腳本就會當成
# 錯誤中止，工作排程器只看到結束代碼 1，日誌裡也只留下「啟動後端」那一行。
# 這段改成 Continue，讓 stderr 單純當文字收進日誌。
$ErrorActionPreference = "Continue"

# 不加 --reload：那是開發用的，檔案一存檔就重啟，
# 正在進行的爬取會被中止，對外服務也會短暫斷線。
& $Python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 2>&1 |
    ForEach-Object { "[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $_ } |
    Out-File -FilePath $LogFile -Append -Encoding utf8
