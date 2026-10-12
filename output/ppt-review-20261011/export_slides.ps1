# 以 PowerPoint 將簡報每頁匯出成 PNG，供視覺檢查。
# 用法：powershell -File export_slides.ps1 -In deck.pptx -OutDir 資料夾 [-Width 1600]
param([string]$In, [string]$OutDir, [int]$Width = 1600)
$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force $OutDir | Out-Null
$app = New-Object -ComObject PowerPoint.Application
try {
    $pres = $app.Presentations.Open((Resolve-Path $In).Path, $true, $false, $false)
    $h = [int]($Width * $pres.PageSetup.SlideHeight / $pres.PageSetup.SlideWidth)
    foreach ($s in $pres.Slides) {
        $s.Export((Join-Path (Resolve-Path $OutDir).Path ("{0:D2}.png" -f $s.SlideIndex)), "PNG", $Width, $h)
    }
    Write-Output "slides=$($pres.Slides.Count)"
    $pres.Close()
} finally {
    $app.Quit()
}
