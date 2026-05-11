from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

logger = logging.getLogger(__name__)


class HistoryStore(Protocol):
    def save_success(self, *, url: str, response: dict[str, Any]) -> UUID | None:
        ...

    def save_error(self, *, url: str, error: str) -> UUID | None:
        ...

    def list_recent(self, *, limit: int = 25) -> list["HistoryItem"]:
        ...


@dataclass(frozen=True)
class HistoryItem:
    id: UUID
    created_at: datetime
    url: str
    status: str
    response: dict[str, Any] | None
    error: str | None


class DisabledHistoryStore:
    def save_success(self, *, url: str, response: dict[str, Any]) -> UUID | None:
        return None

    def save_error(self, *, url: str, error: str) -> UUID | None:
        return None

    def list_recent(self, *, limit: int = 25) -> list[HistoryItem]:
        return []


class PostgresHistoryStore:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self._schema_ready = False

    def save_success(self, *, url: str, response: dict[str, Any]) -> UUID | None:
        return self._insert(url=url, status="ok", response=response, error=None)

    def save_error(self, *, url: str, error: str) -> UUID | None:
        return self._insert(url=url, status="error", response=None, error=error)

    def list_recent(self, *, limit: int = 25) -> list[HistoryItem]:
        self._ensure_schema()
        safe_limit = max(1, min(limit, 100))
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    select id, created_at, url, status, response, error
                    from query_history
                    order by created_at desc
                    limit %s
                    """,
                    (safe_limit,),
                )
                rows = cursor.fetchall()
        return [
            HistoryItem(
                id=row[0],
                created_at=row[1],
                url=row[2],
                status=row[3],
                response=row[4],
                error=row[5],
            )
            for row in rows
        ]

    def _insert(self, *, url: str, status: str, response: dict[str, Any] | None, error: str | None) -> UUID | None:
        try:
            from psycopg.types.json import Jsonb

            self._ensure_schema()
            with self._connect() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        insert into query_history (url, status, response, error)
                        values (%s, %s, %s, %s)
                        returning id
                        """,
                        (url, status, Jsonb(response) if response is not None else None, error),
                    )
                    row = cursor.fetchone()
                    conn.commit()
            return row[0] if row else None
        except Exception:
            logger.warning("Could not save query history", exc_info=True)
            return None

    def _ensure_schema(self) -> None:
        if self._schema_ready:
            return
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    create table if not exists query_history (
                        id uuid primary key default gen_random_uuid(),
                        created_at timestamptz not null default now(),
                        url text not null,
                        status text not null check (status in ('ok', 'error')),
                        response jsonb,
                        error text
                    )
                    """
                )
                cursor.execute("alter table query_history enable row level security")
                cursor.execute(
                    """
                    create index if not exists query_history_created_at_idx
                    on query_history (created_at desc)
                    """
                )
                conn.commit()
        self._schema_ready = True

    def _connect(self):
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("Install psycopg to enable query history storage") from exc
        return psycopg.connect(self.database_url, autocommit=False)
