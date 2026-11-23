"""The one place a database driver is imported (`.importlinter` contract 6).

Connection settings come from infra/.env so that the scripts, the containers and
the Python code cannot disagree about which cluster they mean.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

import psycopg

_ENV_LOADED = False


def _load_env() -> None:
    """Read infra/.env without adding a dependency for six key=value lines."""
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    env = Path(__file__).resolve().parents[2] / "infra" / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())
    _ENV_LOADED = True


def dsn() -> str:
    """Every connection plans each statement for its own parameters (`plan_cache_mode = force_custom_plan`, D-126).

    psycopg prepares a statement on the server after five executions, and Postgres may then reuse a generic plan.
    Under a generic plan pg_search 0.25.6's operators are not exact: the match-all title search (`&&&`) returned
    laws missing its words ('Pakistan Penal Code' put the Constitution first, so every s.302 PPC citation of a
    linker run went unresolved), or failed with 'unrecognized node type'. A custom plan is exact and repeatable,
    with or without parallel workers. Planning each statement costs well under a millisecond here."""
    _load_env()
    return (
        f"host={os.environ.get('POSTGRES_HOST', 'localhost')} "
        f"port={os.environ.get('POSTGRES_PORT', '5433')} "
        f"dbname={os.environ.get('POSTGRES_DB', 'nizam_clean')} "
        f"user={os.environ.get('POSTGRES_USER', 'nizam')} "
        f"password={os.environ.get('POSTGRES_PASSWORD', '')} "
        f"options='-c plan_cache_mode=force_custom_plan'"
    )


@contextmanager
def connect(autocommit: bool = False):
    """A connection that commits on success and rolls back on any exception."""
    conn = psycopg.connect(dsn(), autocommit=autocommit)
    try:
        yield conn
        if not autocommit:
            conn.commit()
    except Exception:
        if not autocommit:
            conn.rollback()
        raise
    finally:
        conn.close()
