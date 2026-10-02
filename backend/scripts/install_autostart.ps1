# 把 MeBOD 後端註冊成「登入時自動啟動」的排程工作。
#
# 用法（一般 PowerShell 即可，不需要系統管理員）：
#     .\scripts\install_autostart.ps1            # 註冊並立即啟動
#     .\scripts\install_autostart.ps1 -Remove    # 移除
#
# 為什麼用排程工作而不是 Windows 服務？
# 爬蟲要開真實瀏覽器視窗，必須待在有桌面的互動工作階段裡；
# Windows 服務跑在 Session 0，沒有桌面。詳見 serve.ps1 的說明。
#
# 公開網址由 cloudflared（Windows 服務，開機自動啟動）轉送到 127.0.0.1:8000。
# cloudflared 會自己起來，但後端先前是手動在終端機執行的——
# 只要忘了開、或關掉那個視窗，外部就會看到 502。這個工作就是補上這一段。

param(
    [switch]$Remove
)

$ErrorActionPreference = "Stop"

$TaskName = "MeBOD Backend"
$BackendDir = Split-Path -Parent $PSScriptRoot
$ServeScript = Join-Path $PSScriptRoot "serve.ps1"

if ($Remove) {
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        "已移除排程工作「$TaskName」。後端需要自行手動啟動。"
    } else {
        "排程工作「$TaskName」原本就不存在。"
    }
    return
}

if (-not (Test-Path $ServeScript)) {
    throw "找不到 $ServeScript"
}

$Action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$ServeScript`"" `
    -WorkingDirectory $BackendDir

# 登入時觸發：工作必須待在互動工作階段，爬蟲才開得了瀏覽器視窗。
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -RestartCount 3 `
    -ExecutionTimeLimit ([TimeSpan]::Zero)

# ExecutionTimeLimit 設為零表示不限時：這是常駐服務，不是會結束的批次工作，
# 預設的三天上限會在第三天把後端殺掉。

$Principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive `
    -RunLevel Limited

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Principal $Principal `
    -Description "MeBOD 後端；由 cloudflared 轉送公開網址。登入時自動啟動。" `
    -Force | Out-Null

"已註冊排程工作「$TaskName」（登入時啟動）。"
"日誌位置：$BackendDir\logs\server-<日期>.log"
"立即啟動請執行： Start-ScheduledTask -TaskName '$TaskName'"
