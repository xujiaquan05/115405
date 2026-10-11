# 以 Word 將 docx 轉成 PDF，並回報頁數（系統簡介規定最多 2 頁）。
param([string]$In, [string]$Out)
$ErrorActionPreference = "Stop"
$word = New-Object -ComObject Word.Application
$word.Visible = $false
try {
    $doc = $word.Documents.Open((Resolve-Path $In).Path, $false, $true)
    $pages = $doc.ComputeStatistics(2)
    $doc.ExportAsFixedFormat($Out, 17)
    $doc.Close($false)
    Write-Output "pages=$pages"
} finally {
    $word.Quit()
}
