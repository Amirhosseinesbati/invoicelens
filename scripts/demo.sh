#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_ROOT="$PROJECT_ROOT/apps/api"
WEB_ROOT="$PROJECT_ROOT/apps/web"
SIZE="${1:-fast}"
if [[ "$SIZE" != fast && "$SIZE" != full ]]; then
  echo 'Usage: bash scripts/demo.sh [fast|full] [--reset] [--prepare-only]' >&2
  exit 2
fi
RESET=0
PREPARE_ONLY=0
for option in "${@:2}"; do
  case "$option" in
    --reset) RESET=1 ;;
    --prepare-only) PREPARE_ONLY=1 ;;
    *) echo "Unknown option: $option" >&2; exit 2 ;;
  esac
done

export UV_CACHE_DIR="$PROJECT_ROOT/.uv-cache"
export UV_PYTHON_INSTALL_DIR="$PROJECT_ROOT/.uv-python"
mkdir -p "$PROJECT_ROOT/tmp"
export TMPDIR="$PROJECT_ROOT/tmp"
export INVOICELENS_MODE=DEMO
export INVOICELENS_DATABASE_URL="sqlite:///$PROJECT_ROOT/data/invoicelens.db"
export INVOICELENS_STORAGE_ROOT="$PROJECT_ROOT/data/uploads"
export INVOICELENS_CHECKPOINT_PATH="$PROJECT_ROOT/data/graph-checkpoints.sqlite"
export INVOICELENS_SECRET_KEY=local-demo-only-invoicelens-key-change-for-connected
export INVOICELENS_COOKIE_SECURE=false
export INVOICELENS_ALLOWED_ORIGIN=http://127.0.0.1:5789
export INVOICELENS_AUTO_WORKER=true
export INVOICELENS_OCR_LANGUAGE=eng
export VITE_API_PROXY_TARGET=http://127.0.0.1:8790
mkdir -p "$PROJECT_ROOT/data"

uv sync --project "$API_ROOT" --python "${INVOICELENS_PYTHON:-3.12}" --frozen
API_PYTHON="$API_ROOT/.venv/bin/python"
if [[ "$SIZE" == full ]]; then
  OUTPUT="$PROJECT_ROOT/generated/invoicelens"
else
  OUTPUT="$PROJECT_ROOT/generated/invoicelens-fast"
fi
MANIFEST="$OUTPUT/manifest.json"
if [[ ! -f "$MANIFEST" ]]; then
  "$API_PYTHON" "$PROJECT_ROOT/scripts/generate_dataset.py" --preset "$SIZE" --output "$OUTPUT"
fi
"$API_PYTHON" -m alembic -c "$API_ROOT/alembic.ini" upgrade head
if [[ "$RESET" == 1 ]]; then
  if [[ "$SIZE" == fast ]]; then
    "$API_PYTHON" -m invoicelens.seed --manifest "$MANIFEST" --reset --only-type purchase_order --process-first 4
  else
    "$API_PYTHON" -m invoicelens.seed --manifest "$MANIFEST" --reset
  fi
else
  if [[ "$SIZE" == fast ]]; then
    "$API_PYTHON" -m invoicelens.seed --manifest "$MANIFEST" --only-type purchase_order --process-first 4
  else
    "$API_PYTHON" -m invoicelens.seed --manifest "$MANIFEST"
  fi
fi
pnpm -C "$WEB_ROOT" install --frozen-lockfile
if [[ "$PREPARE_ONLY" == 1 ]]; then
  echo "DEMO prepared ($SIZE)."
  exit 0
fi

"$API_PYTHON" -m uvicorn invoicelens.main:app --host 127.0.0.1 --port 8790 >"$PROJECT_ROOT/data/api.stdout.log" 2>"$PROJECT_ROOT/data/api.stderr.log" &
API_PID=$!
trap 'kill "$API_PID" 2>/dev/null || true' EXIT INT TERM
echo 'InvoiceLens DEMO: http://127.0.0.1:5789'
pnpm -C "$WEB_ROOT" dev --host 127.0.0.1 --port 5789 --strictPort
