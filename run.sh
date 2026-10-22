#!/usr/bin/env bash
# Executa o Lurdens direto da pasta do projeto, sem instalar.
# Usa o venv local (.venv) se existir; senão, o python3 do sistema.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY=python3
[[ -x "$HERE/.venv/bin/python" ]] && PY="$HERE/.venv/bin/python"
export PYTHONPATH="$HERE${PYTHONPATH:+:$PYTHONPATH}"
exec "$PY" -m lurdens "$@"
