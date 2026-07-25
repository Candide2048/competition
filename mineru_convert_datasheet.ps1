$ErrorActionPreference = "Stop"
$token = $env:MINERU_API_TOKEN
if (-not $token) { $token = [Environment]::GetEnvironmentVariable("MINERU_API_TOKEN","User") }
if (-not $token) { Write-Host "NO_TOKEN"; exit 1 }

$headers = @{ "Content-Type" = "application/json"; "Authorization" = "Bearer $token" }
$inputFile = "D:\Pythonfiles\pythonProject\shipping_wasp\data\Datasheets_Norsepower_CN_v2.pdf"
$inputName = Split-Path $inputFile -Leaf
$outDir = "D:\Pythonfiles\pythonProject\shipping_wasp\data\Datasheets_Norsepower_mineru_output"

# Step 1: request upload URL
$body = @{ files = @(@{ name = $inputName; data_id = "norsepower-ds-001" }); model_version = "vlm"; language = "ch" } | ConvertTo-Json -Depth 4
$resp = Invoke-RestMethod -Method Post -Uri "https://mineru.net/api/v4/file-urls/batch" -Headers $headers -Body $body
$batchId = $resp.data.batch_id
$uploadUrl = $resp.data.file_urls[0]
Write-Host "BATCH_ID=$batchId"

# Step 2: upload file (PUT raw bytes, no auth header)
$fileBytes = [System.IO.File]::ReadAllBytes($inputFile)
Invoke-RestMethod -Method Put -Uri $uploadUrl -Body $fileBytes | Out-Null
Write-Host "UPLOADED"

# Step 3: poll batch results
$zipUrl = $null
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Seconds 5
    $r = Invoke-RestMethod -Method Get -Uri "https://mineru.net/api/v4/extract-results/batch/$batchId" -Headers $headers
    $item = $r.data.extract_result[0]
    $state = $item.state
    Write-Host "state=$state"
    if ($state -eq "done") { $zipUrl = $item.full_zip_url; break }
    if ($state -eq "failed") { Write-Host "FAILED: $($item.err_msg)"; exit 1 }
}
if (-not $zipUrl) { Write-Host "TIMEOUT"; exit 1 }

# Step 4: download and extract
$zip = "$env:TEMP\norsepower-ds.zip"
Invoke-WebRequest -Uri $zipUrl -OutFile $zip
if (-not (Test-Path $outDir)) { New-Item -ItemType Directory -Path $outDir | Out-Null }
Expand-Archive -Path $zip -DestinationPath $outDir -Force
Remove-Item $zip
Write-Host "DONE=$outDir"
