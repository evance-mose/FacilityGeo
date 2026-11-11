"""psycopg2 connection pool and a small cursor helper."""
from contextlib import contextmanager
from typing import Iterator, Optional

from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool

from .config import get_settings

_pool: Optional[ThreadedConnectionPool] = None


def open_pool() -> None:
    global _pool
    s = get_settings()
    _pool = ThreadedConnectionPool(
        s.db_pool_min, s.db_pool_max,
        host=s.db_host, port=s.db_port, dbname=s.db_name, user=s.db_user, password=s.db_password,
        connect_timeout=5,
    )


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.closeall()
        _pool = None


@contextmanager
def cursor(commit: bool = False) -> Iterator[RealDictCursor]:
    """Borrow a pooled connection. Reads are rolled back (ending the
    transaction); writes pass commit=True. Always parameterised SQL."""
    if _pool is None:
        raise RuntimeError("database pool is not open")
    conn = _pool.getconn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur
        if commit:
            conn.commit()
        else:
            conn.rollback()
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)
