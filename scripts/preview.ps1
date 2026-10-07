param(
    [ValidateRange(1024, 65535)][int]$WebPort = 4312,
    [ValidateRange(1024, 65535)][int]$ApiPort = 8312
)

# Uses existing dependencies and a separate synthetic preview database.
# Does not install packages, reset the original demo, or call paid providers.
$ErrorActionPreference = 'Stop'
$project = Split-Path $PSScriptRoot -Parent
$web = Join-Path $project 'apps/web'
$python = Join-Path $project 'apps/api/.venv/Scripts/python.exe'
$vite = Join-Path $web 'node_modules/vite/bin/vite.js'
$manifest = Join-Path $project 'generated/invoicelens-fast/manifest.json'
if (-not (Test-Path -LiteralPath $python)) { throw 'Prepare the locked API dependencies first with scripts/demo.ps1 -PrepareOnly.' }
if (-not (Test-Path -LiteralPath $vite)) { throw 'Web dependencies are absent or have stale junctions. Install the locked dependencies, or inspect scripts/repair-web-links.mjs for a moved Windows checkout.' }
foreach ($port in @($WebPort, $ApiPort)) {
    if (Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue) { throw "Port $port is already occupied. Choose another port; existing processes will not be stopped." }
}
$state = Join-Path $project 'data/preview'
New-Item -ItemType Directory -Force -Path $state | Out-Null
$env:INVOICELENS_MODE = 'DEMO'
$env:PYTHONPATH = Join-Path $project 'apps/api/src'
$env:INVOICELENS_DATABASE_URL = 'sqlite:///' + ((Join-Path $state 'invoicelens.db').Replace('\', '/'))
$env:INVOICELENS_STORAGE_ROOT = Join-Path $state 'uploads'
$env:INVOICELENS_CHECKPOINT_PATH = Join-Path $state 'checkpoints.sqlite'
$env:INVOICELENS_SECRET_KEY = 'local-preview-only-change-before-connected-mode'
$env:INVOICELENS_COOKIE_SECURE = 'false'
$env:INVOICELENS_ALLOWED_ORIGIN = "http://127.0.0.1:$WebPort"
$env:INVOICELENS_AUTO_WORKER = 'true'
$env:VITE_API_PROXY_TARGET = "http://127.0.0.1:$ApiPort"
$env:OMP_THREAD_LIMIT = '1'
$portableOcr = Join-Path $project 'tmp/tesseract-ocr'
if (Test-Path -LiteralPath (Join-Path $portableOcr 'tesseract.exe')) { $env:PATH = $portableOcr + ';' + $env:PATH }
Push-Location $project
try {
    if (Test-Path -LiteralPath $manifest) {
        & $python -m invoicelens.seed --manifest $manifest --only-type purchase_order --process-first 4
        if ($LASTEXITCODE -ne 0) { throw 'Could not seed the isolated preview workspace.' }
    }
    $api = Start-Process -FilePath $python -ArgumentList @('-m','uvicorn','invoicelens.main:app','--host','127.0.0.1','--port',"$ApiPort") -WorkingDirectory $project -PassThru -WindowStyle Hidden -RedirectStandardOutput (Join-Path $state 'api.stdout.log') -RedirectStandardError (Join-Path $state 'api.stderr.log')
    try {
        Write-Host "InvoiceLens synthetic preview: http://127.0.0.1:$WebPort"
        Write-Host 'Use demo operator at login. Upload generated/invoicelens-fast/documents/INV-*.pdf.'
        Set-Location $web
        & node $vite --host 127.0.0.1 --port $WebPort --strictPort
        if ($LASTEXITCODE -ne 0) { throw 'The preview web server stopped with an error.' }
    } finally { if (-not $api.HasExited) { Stop-Process -Id $api.Id } }
} finally { Pop-Location }
