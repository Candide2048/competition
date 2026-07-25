$ErrorActionPreference = "Stop"
$token = $env:MINERU_API_TOKEN
if (-not $token) { $token = [Environment]::GetEnvironmentVariable("MINERU_API_TOKEN","User") }
$headers = @{ "Content-Type" = "application/json"; "Authorization" = "Bearer $token" }
$batchId = "7ac1640e-827d-413a-9760-120155d783fe"
$outDir = "D:\Pythonfiles\pythonProject\shipping_wasp\data\Datasheets_Norsepower_mineru_output"

$r = Invoke-RestMethod -Method Get -Uri "https://mineru.net/api/v4/extract-results/batch/$batchId" -Headers $headers
$zipUrl = $r.data.extract_result[0].full_zip_url
Write-Host "ZIP_URL_OK"

$zip = "$env:TEMP\norsepower-ds.zip"
$ok = $false
for ($i = 1; $i -le 5; $i++) {
    try {
        Invoke-WebRequest -Uri $zipUrl -OutFile $zip -TimeoutSec 180
        $ok = $true; break
    } catch {
        Write-Host "retry $i failed"
        Start-Sleep -Seconds 3
    }
}
if (-not $ok) { Write-Host "DOWNLOAD_FAILED"; exit 1 }
if (-not (Test-Path $outDir)) { New-Item -ItemType Directory -Path $outDir | Out-Null }
Expand-Archive -Path $zip -DestinationPath $outDir -Force
Remove-Item $zip
Write-Host "DONE=$outDir"
Get-ChildItem -Recurse $outDir | Select-Object FullName
