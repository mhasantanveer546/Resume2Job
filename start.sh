#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
printf '\nOpen http://127.0.0.1:8000 in your browser. Press Ctrl+C to stop.\n'
exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
