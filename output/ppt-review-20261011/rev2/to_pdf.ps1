param([string]$In, [string]$Out)
$ErrorActionPreference = "Stop"
$app = New-Object -ComObject PowerPoint.Application
try {
    $pres = $app.Presentations.Open((Resolve-Path $In).Path, $true, $false, $false)
    $pres.SaveAs($Out, 32)
    $pres.Close()
} finally { $app.Quit() }
