#!/bin/bash
# Start the Ekonomi finance app on http://localhost:8040
cd "$(dirname "$0")"
if [ ! -d venv ]; then
  python3 -m venv venv
  ./venv/bin/pip install -r requirements.txt
fi
exec ./venv/bin/uvicorn server.main:app --host 127.0.0.1 --port 8040 "$@"
