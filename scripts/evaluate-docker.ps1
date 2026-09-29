param(
    [ValidateRange(1, 100)][int]$Batches = 15,
    [ValidateRange(1, 40)][int]$BatchSize = 20,
    [string]$DatabaseName = 'invoicelens-ocr-final-batched.db',
    [string]$Image = 'newfolder2-api'
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$database = Join-Path $projectRoot (Join-Path 'evals/results' $DatabaseName)
if ($DatabaseName -ne [IO.Path]::GetFileName($DatabaseName)) {
    throw 'DatabaseName must be a filename inside evals/results.'
}
if (-not (Test-Path -LiteralPath $database)) {
    throw "Seeded evaluation database missing: $database"
}
$bind = "type=bind,source=$projectRoot,target=/workspace"
$containerDatabase = "/workspace/evals/results/$DatabaseName"

for ($batch = 1; $batch -le $Batches; $batch++) {
    $free = (Get-PSDrive C).Free
    if ($free -lt 2GB) {
        throw "C: has less than 2 GB free before batch $batch; stop and recover disk space."
    }
    Write-Host "OCR batch $batch/$Batches (up to $BatchSize jobs; two CPU cores, 2 GB RAM)"
    & docker run --rm --cpus=2 --memory=2g --mount $bind -w /workspace `
        -e OMP_THREAD_LIMIT=1 -e OMP_NUM_THREADS=1 -e TMPDIR=/workspace/evals/results/tmp `
        $Image python evals/process_queued.py --database $containerDatabase --limit $BatchSize
    if ($LASTEXITCODE -ne 0) {
        throw "OCR batch $batch failed. The seeded database is preserved for inspection."
    }
}

$apiPython = Join-Path $projectRoot 'apps/api/.venv/Scripts/python.exe'
$statusOutput = & $apiPython (Join-Path $projectRoot 'evals/export_demo_predictions.py') --database $database --status-only
if ($LASTEXITCODE -ne 0) { throw 'Could not inspect evaluation job statuses.' }
$statuses = ($statusOutput | Out-String | ConvertFrom-Json).processing_statuses
if ($statuses.complete -ne 300) {
    throw "Evaluation is incomplete: $($statuses | ConvertTo-Json -Compress). Preserve the database and resume batches."
}
& $apiPython (Join-Path $projectRoot 'evals/run_demo_evaluation.py') --skip-processing --database $database
if ($LASTEXITCODE -ne 0) { throw 'Prediction export or scoring failed.' }
