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
    _load_env()
    return (
        f"host={os.environ.get('POSTGRES_HOST', 'localhost')} "
        f"port={os.environ.get('POSTGRES_PORT', '5433')} "
        f"dbname={os.environ.get('POSTGRES_DB', 'nizam_clean')} "
        f"user={os.environ.get('POSTGRES_USER', 'nizam')} "
        f"password={os.environ.get('POSTGRES_PASSWORD', '')}"
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
