$ErrorActionPreference = 'Stop'
$documentPath = Join-Path (Split-Path $PSScriptRoot) 'MeBOD_115年系統手冊_大學部物件導向修訂版.docx'
$pdfPath = Join-Path $PSScriptRoot 'undergraduate-final.pdf'
$wordApp = New-Object -ComObject Word.Application
$wordApp.Visible = $false
$wordApp.DisplayAlerts = 0
$manualDoc = $null
try {
  $manualDoc = $wordApp.Documents.Open($documentPath, $false, $false)
  $manualDoc.Fields.Update() | Out-Null
  $manualDoc.Repaginate()
  foreach ($tocItem in $manualDoc.TablesOfContents) { $tocItem.Update() }
  $manualDoc.Fields.Update() | Out-Null
  $manualDoc.Repaginate()
  $manualDoc.Fields.Update() | Out-Null
  $manualDoc.Save()
  $manualDoc.ExportAsFixedFormat($pdfPath, 17)
  Write-Output ('Pages: ' + $manualDoc.ComputeStatistics(2))
  $manualDoc.Close(0)
  $manualDoc = $null
} finally {
  if ($null -ne $manualDoc) { $manualDoc.Close(0) }
  $wordApp.Quit()
}
