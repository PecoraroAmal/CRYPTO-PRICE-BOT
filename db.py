import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from config import DB_PATH

INITIAL_SYMBOL_MAPPING = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "LTC": "litecoin",
    "XRP": "ripple",
    "AVAX": "avalanche-2",
}


@contextmanager
def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                threshold REAL NOT NULL,
                currency TEXT NOT NULL,
                current_state TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS symbol_mapping (
                symbol TEXT PRIMARY KEY,
                coingecko_id TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS api_usage (
                month TEXT PRIMARY KEY,
                calls_count INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS step_state (
                symbol TEXT NOT NULL,
                currency TEXT NOT NULL,
                last_bucket INTEGER NOT NULL,
                PRIMARY KEY (symbol, currency)
            )
            """
        )
        count = conn.execute("SELECT COUNT(*) FROM symbol_mapping").fetchone()[0]
        if count == 0:
            conn.executemany(
                "INSERT INTO symbol_mapping (symbol, coingecko_id) VALUES (?, ?)",
                INITIAL_SYMBOL_MAPPING.items(),
            )


# --- symbol mapping ---

def get_coingecko_id(symbol: str) -> str | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT coingecko_id FROM symbol_mapping WHERE symbol = ?",
            (symbol.upper(),),
        ).fetchone()
        return row["coingecko_id"] if row else None


def list_symbol_mappings() -> list[sqlite3.Row]:
    with _connect() as conn:
        return conn.execute(
            "SELECT symbol, coingecko_id FROM symbol_mapping ORDER BY symbol"
        ).fetchall()


# --- alerts ---

def add_alert(symbol: str, direction: str, threshold: float, currency: str, current_state: str):
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO alerts (symbol, direction, threshold, currency, current_state, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (symbol.upper(), direction, threshold, currency.upper(), current_state,
             datetime.now(timezone.utc).isoformat()),
        )


def list_alerts() -> list[sqlite3.Row]:
    with _connect() as conn:
        return conn.execute("SELECT * FROM alerts ORDER BY id").fetchall()


def remove_alert_by_position(position: int) -> bool:
    alerts = list_alerts()
    if position < 1 or position > len(alerts):
        return False
    alert_id = alerts[position - 1]["id"]
    with _connect() as conn:
        conn.execute("DELETE FROM alerts WHERE id = ?", (alert_id,))
    return True


def update_alert_state(alert_id: int, new_state: str):
    with _connect() as conn:
        conn.execute(
            "UPDATE alerts SET current_state = ? WHERE id = ?",
            (new_state, alert_id),
        )


# --- api usage ---

def _current_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def increment_api_usage():
    month = _current_month()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO api_usage (month, calls_count) VALUES (?, 1)
            ON CONFLICT(month) DO UPDATE SET calls_count = calls_count + 1
            """,
            (month,),
        )


def get_api_usage() -> int:
    month = _current_month()
    with _connect() as conn:
        row = conn.execute(
            "SELECT calls_count FROM api_usage WHERE month = ?", (month,)
        ).fetchone()
        return row["calls_count"] if row else 0


# --- step (livello) state ---

def get_step_bucket(symbol: str, currency: str) -> int | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT last_bucket FROM step_state WHERE symbol = ? AND currency = ?",
            (symbol, currency),
        ).fetchone()
        return row["last_bucket"] if row else None


def set_step_bucket(symbol: str, currency: str, bucket: int):
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO step_state (symbol, currency, last_bucket) VALUES (?, ?, ?)
            ON CONFLICT(symbol, currency) DO UPDATE SET last_bucket = excluded.last_bucket
            """,
            (symbol, currency, bucket),
        )
