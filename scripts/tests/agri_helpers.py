"""Shared helper functions for AgricultureClaw unit tests.

Provides:
  - DB bootstrap via init_schema.init_db() + agricultureclaw init_db
  - call_action() / ns() / is_error() / is_ok()
  - Seed functions for company, naming series
  - load_db_query() for explicit module loading (avoids sys.path collisions)
  - build_env() for a complete agriculture test environment
"""
import argparse
import importlib.util
import io
import json
import os
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch

# ──────────────────────────────────────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────────────────────────────────────

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
MODULE_DIR = os.path.dirname(TESTS_DIR)  # agricultureclaw/scripts/
SCRIPTS_DIR = MODULE_DIR                  # db_query.py lives here
AGRI_ROOT = os.path.dirname(MODULE_DIR)   # agricultureclaw/
# Foundation init_schema.py
SRC_DIR = os.path.dirname(AGRI_ROOT)  # source/
SETUP_DIR = os.path.join(SRC_DIR, "erpclaw", "scripts", "erpclaw-setup")
INIT_SCHEMA_PATH = os.path.join(SETUP_DIR, "init_schema.py")
AGRI_INIT_PATH = os.path.join(AGRI_ROOT, "init_db.py")

# Make erpclaw_lib importable
# M54: bind erpclaw_lib to the tree under test, never the deployed
# ~/.openclaw/erpclaw/lib symlink — the last install to run wins that symlink,
# so with several worktrees in flight it resolves to a tree nobody is testing
# (and DANGLES once that worktree is removed). The deployed install stays as
# the fallback for a published module repo, which ships no source/erpclaw/.
_IN_TREE_LIB = os.path.join(SETUP_DIR, "lib")
ERPCLAW_LIB = (_IN_TREE_LIB if os.path.isdir(os.path.join(_IN_TREE_LIB, "erpclaw_lib"))
               else os.path.join(os.path.expanduser(
                   os.environ.get("ERPCLAW_HOME", "~/.openclaw/erpclaw")), "lib"))
if ERPCLAW_LIB not in sys.path:
    if importlib.util.find_spec("erpclaw_lib") is None:
        sys.path.insert(0, ERPCLAW_LIB)

from erpclaw_lib.db import setup_pragmas


def load_db_query():
    """Load agricultureclaw's db_query.py explicitly to avoid sys.path collisions."""
    db_query_path = os.path.join(SCRIPTS_DIR, "db_query.py")
    spec = importlib.util.spec_from_file_location("db_query_agri", db_query_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ──────────────────────────────────────────────────────────────────────────────
# DB helpers
# ──────────────────────────────────────────────────────────────────────────────

def init_all_tables(db_path: str):
    """Create all foundation tables + agricultureclaw vertical tables."""
    # Foundation tables
    spec = importlib.util.spec_from_file_location("init_schema", INIT_SCHEMA_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.init_db(db_path)

    # AgricultureClaw vertical tables
    spec2 = importlib.util.spec_from_file_location("agri_init_db", AGRI_INIT_PATH)
    mod2 = importlib.util.module_from_spec(spec2)
    spec2.loader.exec_module(mod2)
    mod2.create_agricultureclaw_tables(db_path)


class _ConnWrapper:
    """Wraps a sqlite3.Connection to support conn.company_id attribute
    used by erpclaw_lib.naming.get_next_name()."""

    def __init__(self, real_conn: sqlite3.Connection):
        self._conn = real_conn
        self.company_id = None
        self.row_factory = real_conn.row_factory

    def execute(self, sql, params=()):
        return self._conn.execute(sql, params)

    def executemany(self, sql, params_seq):
        return self._conn.executemany(sql, params_seq)

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        return self._conn.close()

    def cursor(self):
        return self._conn.cursor()

    def create_aggregate(self, name, n, cls):
        return self._conn.create_aggregate(name, n, cls)

    @property
    def in_transaction(self):
        return self._conn.in_transaction

    def __enter__(self):
        return self._conn.__enter__()

    def __exit__(self, *args):
        return self._conn.__exit__(*args)


class _DecimalSum:
    """Custom SQLite aggregate: SUM using Python Decimal for precision."""
    def __init__(self):
        self.total = Decimal("0")
    def step(self, value):
        if value is not None:
            self.total += Decimal(str(value))
    def finalize(self):
        return str(self.total)


def get_conn(db_path: str) -> _ConnWrapper:
    """Return a wrapped sqlite3.Connection with FK enabled and Row factory."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    setup_pragmas(conn)
    conn.create_aggregate("decimal_sum", 1, _DecimalSum)
    return _ConnWrapper(conn)


# ──────────────────────────────────────────────────────────────────────────────
# Action invocation helpers
# ──────────────────────────────────────────────────────────────────────────────

def call_action(fn, conn, args) -> dict:
    """Invoke a domain function, capture stdout JSON, return parsed dict."""
    buf = io.StringIO()

    def _fake_exit(code=0):
        raise SystemExit(code)

    try:
        with patch("sys.stdout", buf), patch("sys.exit", side_effect=_fake_exit):
            fn(conn, args)
    except SystemExit:
        pass

    output = buf.getvalue().strip()
    if not output:
        return {"status": "error", "message": "no output captured"}
    return json.loads(output)


def ns(**kwargs) -> argparse.Namespace:
    """Build an argparse.Namespace from keyword args (mimics CLI flags)."""
    return argparse.Namespace(**kwargs)


def is_error(result: dict) -> bool:
    """Check if a call_action result is an error response."""
    return result.get("status") == "error"


def is_ok(result: dict) -> bool:
    """Check if a call_action result is a success response."""
    return result.get("status") == "ok"


# ──────────────────────────────────────────────────────────────────────────────
# Utility
# ──────────────────────────────────────────────────────────────────────────────

def _uuid() -> str:
    return str(uuid.uuid4())


# ──────────────────────────────────────────────────────────────────────────────
# Seed helpers
# ──────────────────────────────────────────────────────────────────────────────

def seed_company(conn, name="Test Farm", abbr="TF") -> str:
    """Insert a test company via direct SQL and return its ID."""
    cid = _uuid()
    conn.execute(
        """INSERT INTO company (id, name, abbr, default_currency, country,
           fiscal_year_start_month)
           VALUES (?, ?, ?, 'USD', 'United States', 1)""",
        (cid, f"{name} {cid[:6]}", f"{abbr}{cid[:4]}")
    )
    conn.commit()
    return cid


def seed_naming_series(conn, company_id: str):
    """Seed naming series for agricultureclaw entity types."""
    series = [
        ("parcel", "PRC-", 0),
        ("planting_plan", "PP-", 0),
        ("field_operation", "FOP-", 0),
        ("harvest_record", "HRV-", 0),
        ("animal", "ANM-", 0),
        ("coop_member", "COOP-", 0),
        ("delivery_ticket", "DT-", 0),
    ]
    for entity_type, prefix, current in series:
        conn.execute(
            """INSERT OR IGNORE INTO naming_series
               (id, entity_type, prefix, current_value, company_id)
               VALUES (?, ?, ?, ?, ?)""",
            (_uuid(), entity_type, prefix, current, company_id)
        )
    conn.commit()


def seed_account(conn, company_id: str, name="Test Account",
                 root_type="asset", account_type=None,
                 account_number=None) -> str:
    """Insert a GL account and return its ID."""
    aid = _uuid()
    direction = "debit_normal" if root_type in ("asset", "expense") else "credit_normal"
    conn.execute(
        """INSERT INTO account (id, name, account_number, root_type, account_type,
           balance_direction, company_id, depth)
           VALUES (?, ?, ?, ?, ?, ?, ?, 0)""",
        (aid, name, account_number or f"ACC-{aid[:6]}", root_type,
         account_type, direction, company_id)
    )
    conn.commit()
    return aid


def seed_fiscal_year(conn, company_id: str, name=None,
                     start="2026-01-01", end="2026-12-31") -> str:
    """Insert a fiscal year and return its ID."""
    fid = _uuid()
    conn.execute(
        """INSERT INTO fiscal_year (id, name, start_date, end_date, company_id)
           VALUES (?, ?, ?, ?, ?)""",
        (fid, name or f"FY-{fid[:6]}", start, end, company_id)
    )
    conn.commit()
    return fid


def seed_cost_center(conn, company_id: str, name="Main CC") -> str:
    """Insert a cost center and return its ID."""
    ccid = _uuid()
    conn.execute(
        """INSERT INTO cost_center (id, name, company_id, is_group)
           VALUES (?, ?, ?, 0)""",
        (ccid, name, company_id)
    )
    conn.commit()
    return ccid


def build_env(conn) -> dict:
    """Create a full agriculture test environment.

    Returns dict with: company_id, plus naming series ready.
    """
    cid = seed_company(conn)
    seed_naming_series(conn, cid)
    fyid = seed_fiscal_year(conn, cid)
    ccid = seed_cost_center(conn, cid)
    revenue_acct = seed_account(conn, cid, "Agri Revenue", "income", "revenue", "4000")
    receivable_acct = seed_account(conn, cid, "Accounts Receivable", "asset", "receivable", "1100")
    cogs_acct = seed_account(conn, cid, "COGS", "expense", "cost_of_goods_sold", "5000")
    inventory_acct = seed_account(conn, cid, "Inventory", "asset", "stock", "1200")

    return {
        "company_id": cid,
        "fiscal_year_id": fyid,
        "cost_center_id": ccid,
        "revenue_account_id": revenue_acct,
        "receivable_account_id": receivable_acct,
        "cogs_account_id": cogs_acct,
        "inventory_account_id": inventory_acct,
    }
