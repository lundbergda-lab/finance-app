# Ekonomi — Family Finance Dashboard

Personal/family finance app: import bank & credit-card statements (xlsx/csv/pdf),
AI-powered categorization via the Claude API, dashboards for spending, cash flow,
budget, loans, and balance sheet.

Ported 1:1 from a single-file HTML prototype to a proper app:

- **Frontend** — the original single-page UI, served from `static/index.html`
  (unchanged apart from the storage layer and API-key handling).
- **Backend** — FastAPI ([server/main.py](server/main.py)).
- **Database** — SQLite, one file at `data/ekonomi.db`, created automatically
  on first run ([server/db.py](server/db.py)). Entity data (transactions,
  accounts, loans, budgets, …) lives in real tables; config-style state
  (payee rules, filter rules, overrides, …) in a key-value settings table.

## Run

```bash
./run.sh
# → http://localhost:8040
```

Or manually:

```bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
./venv/bin/uvicorn server.main:app --port 8040
```

## API key

Copy `.env.example` to `.env` and set `ANTHROPIC_API_KEY`. The backend proxies
all Claude API calls (`/api/anthropic/messages`), so the key never reaches the
browser. If no `.env` key is set, the key entered under Settings → General is
used as fallback (stored in the database).

## Migrating data from the old HTML file

Open the old `ekonomi.html`, go to **Settings → Data → Export JSON backup**,
then in this app use **Settings → Data → Import** to load the backup.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/data` | Full app data object + whether a server key is configured |
| PUT | `/api/data` | Persist the full app data object |
| POST | `/api/anthropic/messages` | Server-side proxy to the Claude API |

## Notes

- `data/` (the SQLite db) and `.env` are gitignored — financial data and
  secrets never enter the repo.
- Saves are debounced client-side (400 ms) and flushed with `sendBeacon`
  on page close.
