param(
    [ValidateSet('fast', 'full')][string]$Size = 'fast',
    [switch]$Reset,
    [switch]$PrepareOnly
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$apiRoot = Join-Path $projectRoot 'apps/api'
$webRoot = Join-Path $projectRoot 'apps/web'
$taskTemp = Join-Path $projectRoot 'tmp'
New-Item -ItemType Directory -Force -Path $taskTemp | Out-Null
$env:TEMP = $taskTemp
$env:TMP = $taskTemp
$env:UV_CACHE_DIR = Join-Path $projectRoot '.uv-cache'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $projectRoot '.uv-python'
$env:INVOICELENS_MODE = 'DEMO'
$env:INVOICELENS_DATABASE_URL = 'sqlite:///' + ((Join-Path $projectRoot 'data/invoicelens.db').Replace('\', '/'))
$env:INVOICELENS_STORAGE_ROOT = Join-Path $projectRoot 'data/uploads'
$env:INVOICELENS_CHECKPOINT_PATH = Join-Path $projectRoot 'data/graph-checkpoints.sqlite'
$env:INVOICELENS_SECRET_KEY = 'local-demo-only-invoicelens-key-change-for-connected'
$env:INVOICELENS_COOKIE_SECURE = 'false'
$env:INVOICELENS_ALLOWED_ORIGIN = 'http://127.0.0.1:5789'
$env:INVOICELENS_AUTO_WORKER = 'true'
$env:INVOICELENS_OCR_LANGUAGE = 'eng'
$env:VITE_API_PROXY_TARGET = 'http://127.0.0.1:8790'
$portableOcr = Join-Path $taskTemp 'tesseract-ocr'
if (-not (Get-Command tesseract -ErrorAction SilentlyContinue) -and
    (Test-Path -LiteralPath (Join-Path $portableOcr 'tesseract.exe')) -and
    (Test-Path -LiteralPath (Join-Path $portableOcr 'tessdata/eng.traineddata'))) {
    $env:PATH = $portableOcr + ';' + $env:PATH
}
$env:OMP_THREAD_LIMIT = '1'

New-Item -ItemType Directory -Force -Path (Join-Path $projectRoot 'data') | Out-Null
$pythonSelector = if ($env:INVOICELENS_PYTHON) { $env:INVOICELENS_PYTHON } else { '3.12' }
& uv sync --project $apiRoot --python $pythonSelector --frozen
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
$apiPython = Join-Path $apiRoot '.venv/Scripts/python.exe'
$outputRelative = if ($Size -eq 'full') { 'generated/invoicelens' } else { 'generated/invoicelens-fast' }
$output = Join-Path $projectRoot $outputRelative
$manifest = Join-Path $output 'manifest.json'
if (-not (Test-Path -LiteralPath $manifest)) {
    & $apiPython (Join-Path $projectRoot 'scripts/generate_dataset.py') --preset $Size --output $output
    if ($LASTEXITCODE -ne 0) { throw 'Synthetic dataset generation failed.' }
}
& $apiPython -m alembic -c (Join-Path $apiRoot 'alembic.ini') upgrade head
if ($LASTEXITCODE -ne 0) { throw 'Database migration failed.' }
$seedArgs = @('-m', 'invoicelens.seed', '--manifest', $manifest)
if ($Reset) { $seedArgs += '--reset' }
if ($Size -eq 'fast') { $seedArgs += @('--only-type', 'purchase_order', '--process-first', '4') }
& $apiPython @seedArgs
if ($LASTEXITCODE -ne 0) { throw 'Demo seeding failed.' }
& pnpm -C $webRoot install --frozen-lockfile
if ($LASTEXITCODE -ne 0) { throw 'Web dependency installation failed.' }

if ($PrepareOnly) {
    Write-Host "DEMO prepared ($Size)."
    exit 0
}

$apiOut = Join-Path $projectRoot 'data/api.stdout.log'
$apiErr = Join-Path $projectRoot 'data/api.stderr.log'
$apiProcess = Start-Process -FilePath $apiPython -ArgumentList @('-m', 'uvicorn', 'invoicelens.main:app', '--host', '127.0.0.1', '--port', '8790') -WorkingDirectory $projectRoot -PassThru -WindowStyle Hidden -RedirectStandardOutput $apiOut -RedirectStandardError $apiErr
try {
    Write-Host 'InvoiceLens DEMO: http://127.0.0.1:5789'
    Write-Host "API log: $apiErr"
    & pnpm -C $webRoot dev --host 127.0.0.1 --port 5789 --strictPort
} finally {
    if (-not $apiProcess.HasExited) { Stop-Process -Id $apiProcess.Id -Force }
}
