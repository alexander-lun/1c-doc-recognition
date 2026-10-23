#!/usr/bin/env bash
# Тесты: поднимает сервис извлечения текста и заглушку API Диадока, запускает pytest против опубликованной базы.
#   BASE_URL=... API_KEY=... scripts/test.sh [аргументы pytest]
#   scripts/test.sh -m service     только сервис, без 1С и модели
#   scripts/test.sh -m llm         распознавание тестовых документов (около минуты на документ)
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON=${PYTHON:-python3}
PORT=${SERVICE_PORT:-8091}

DIADOC_PORT=${DIADOC_PORT:-8092}
export DIADOC_URL=http://127.0.0.1:$DIADOC_PORT

"$PYTHON" -m uvicorn doc_text:app --app-dir service --port "$PORT" --log-level warning &
SERVICE_PID=$!
"$PYTHON" -m uvicorn diadoc_mock:app --app-dir tests --port "$DIADOC_PORT" --log-level warning &
DIADOC_PID=$!
trap 'kill $SERVICE_PID $DIADOC_PID 2>/dev/null' EXIT

for _ in {1..30}; do
  curl -sf -o /dev/null "http://127.0.0.1:$PORT/health" && curl -sf -o /dev/null -X POST "$DIADOC_URL/_test/reset" && break
  sleep 0.5
done

"$PYTHON" -m pytest "$@"
