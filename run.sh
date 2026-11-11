#!/usr/bin/env bash
# Sobe a plataforma Safra Sentinela em http://localhost:8000 (ou na porta de $PORT).
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ]; then
    echo "Criando o ambiente Python (.venv)…"
    python3 -m venv .venv
fi
if ! .venv/bin/python -c "import fastapi, uvicorn" 2>/dev/null; then
    echo "Instalando as dependências…"
    .venv/bin/python -m pip install --quiet -r requirements.txt
fi
if [ ! -f app/data/previsoes.csv ]; then
    echo "Os dados da plataforma não foram encontrados em app/data/."
    echo "Gere-os com:  .venv/bin/pip install -r requirements-analise.txt && .venv/bin/python scripts/preparar_app.py"
    exit 1
fi

PORTA="${PORT:-8000}"
echo "Safra Sentinela em http://localhost:${PORTA}  (Ctrl+C para parar)"
exec .venv/bin/python -m uvicorn app.server:app --host 127.0.0.1 --port "${PORTA}"
