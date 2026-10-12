# 以 Word 更新目錄、圖目錄、表目錄後另存 docx 與 PDF，並回報頁數。
param([string]$In, [string]$OutDocx, [string]$OutPdf)
$ErrorActionPreference = "Stop"
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
    $doc = $word.Documents.Open((Resolve-Path $In).Path, $false, $false)
    foreach ($t in $doc.TablesOfContents) { $t.Update() }
    foreach ($t in $doc.TablesOfFigures) { $t.Update() }
    $doc.Repaginate()
    foreach ($t in $doc.TablesOfContents) { $t.UpdatePageNumbers() }
    foreach ($t in $doc.TablesOfFigures) { $t.UpdatePageNumbers() }
    $pages = $doc.ComputeStatistics(2)
    $doc.SaveAs2($OutDocx, 16)
    $doc.ExportAsFixedFormat($OutPdf, 17)
    $doc.Close($false)
    Write-Output "pages=$pages tocs=ok"
} finally {
    $word.Quit()
}
