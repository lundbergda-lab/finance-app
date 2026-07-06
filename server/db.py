"""SQLite persistence layer for Ekonomi.

The frontend works with one DATA object (same shape as the original
localStorage blob). We decompose it into proper tables for the entity
lists that benefit from SQL, and a key-value settings table for the
config-style rest. Entity rows keep the full original object as JSON
in a `data` column so the round-trip is lossless.
"""
import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "ekonomi.db"

# DATA keys that are lists of objects with an `id` → one table each
ENTITY_TABLES = {
    "transactions": "transactions",
    "groups": "import_groups",
    "accounts": "accounts",
    "creditors": "creditors",
    "manualAssets": "manual_assets",
    "incomes": "incomes",
}

# DATA keys stored as JSON values in the settings table
SETTINGS_KEYS = [
    "payeeRules", "customCategories", "filterRules", "importPeriods",
    "sourceNames", "sourceToAccount", "cashFlowOverrides", "budgetRowTypes",
    "hiddenCreditors", "loanTypeOrder", "apiKey", "currency",
]

DEFAULT_DATA = {
    "transactions": [], "budgets": {}, "groups": [], "accounts": [],
    "payeeRules": {}, "customCategories": [], "filterRules": [],
    "importPeriods": [], "sourceNames": {}, "sourceToAccount": {},
    "creditors": [], "manualAssets": [], "cashFlowOverrides": {},
    "budgetRowTypes": {}, "hiddenCreditors": [], "loanTypeOrder": [],
    "incomes": [], "apiKey": "", "currency": "kr",
}


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    conn = get_conn()
    try:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS transactions (
            id          TEXT PRIMARY KEY,
            date        TEXT,
            description TEXT,
            amount      REAL,
            category    TEXT,
            group_id    TEXT,
            data        TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_txn_date     ON transactions(date);
        CREATE INDEX IF NOT EXISTS idx_txn_category ON transactions(category);
        CREATE INDEX IF NOT EXISTS idx_txn_group    ON transactions(group_id);

        CREATE TABLE IF NOT EXISTS import_groups (id TEXT PRIMARY KEY, data TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS accounts      (id TEXT PRIMARY KEY, data TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS creditors     (id TEXT PRIMARY KEY, data TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS manual_assets (id TEXT PRIMARY KEY, data TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS incomes       (id TEXT PRIMARY KEY, data TEXT NOT NULL);

        CREATE TABLE IF NOT EXISTS budgets (
            month    TEXT NOT NULL,
            category TEXT NOT NULL,
            amount   REAL NOT NULL,
            PRIMARY KEY (month, category)
        );

        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        conn.commit()
    finally:
        conn.close()


def load_data() -> dict:
    """Assemble the full DATA object from the tables."""
    conn = get_conn()
    try:
        data = {k: (v.copy() if isinstance(v, (dict, list)) else v)
                for k, v in DEFAULT_DATA.items()}

        for key, table in ENTITY_TABLES.items():
            rows = conn.execute(f"SELECT data FROM {table}").fetchall()
            data[key] = [json.loads(r[0]) for r in rows]

        budgets: dict = {}
        for month, category, amount in conn.execute(
                "SELECT month, category, amount FROM budgets"):
            budgets.setdefault(month, {})[category] = amount
        data["budgets"] = budgets

        for key, value in conn.execute("SELECT key, value FROM settings"):
            if key in SETTINGS_KEYS:
                data[key] = json.loads(value)

        return data
    finally:
        conn.close()


def save_data(data: dict) -> None:
    """Persist the full DATA object (full replace, one transaction)."""
    conn = get_conn()
    try:
        conn.execute("BEGIN")

        conn.execute("DELETE FROM transactions")
        conn.executemany(
            "INSERT INTO transactions (id, date, description, amount, category, group_id, data)"
            " VALUES (?,?,?,?,?,?,?)",
            [(t.get("id"), t.get("date"), t.get("description"), t.get("amount"),
              t.get("category"), t.get("groupId"), json.dumps(t, ensure_ascii=False))
             for t in data.get("transactions", []) if t.get("id")])

        for key, table in ENTITY_TABLES.items():
            if key == "transactions":
                continue
            conn.execute(f"DELETE FROM {table}")
            conn.executemany(
                f"INSERT INTO {table} (id, data) VALUES (?,?)",
                [(item.get("id"), json.dumps(item, ensure_ascii=False))
                 for item in data.get(key, []) if item.get("id")])

        conn.execute("DELETE FROM budgets")
        conn.executemany(
            "INSERT INTO budgets (month, category, amount) VALUES (?,?,?)",
            [(month, category, amount)
             for month, cats in (data.get("budgets") or {}).items()
             for category, amount in (cats or {}).items()])

        conn.executemany(
            "INSERT INTO settings (key, value) VALUES (?,?)"
            " ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            [(k, json.dumps(data.get(k, DEFAULT_DATA[k]), ensure_ascii=False))
             for k in SETTINGS_KEYS])

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_setting(key: str):
    conn = get_conn()
    try:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else None
    finally:
        conn.close()
