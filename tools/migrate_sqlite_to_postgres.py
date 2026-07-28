"""Import a Sonic R SQLite database into PostgreSQL with count verification.

Run this from Replit Shell after uploading a consistent SQLite snapshot:

    python tools/migrate_sqlite_to_postgres.py \
        results/import/paper_trading.db --replace

The destination URL is read from DATABASE_URL (or SONIC_DATABASE_URL). The URL
is never printed. All destination changes happen in one transaction.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.storage.database import (  # noqa: E402
    connect_database,
    is_postgres_target,
    resolve_database_target,
    scalar,
)


TABLES = (
    "scan_runs",
    "latest_setups",
    "paper_trades",
    "paper_events",
)
DELETE_ORDER = tuple(reversed(TABLES))
IDENTITY_TABLES = ("scan_runs", "paper_trades", "paper_events")


def open_source(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise FileNotFoundError(f"Không tìm thấy SQLite snapshot: {path}")
    uri = f"file:{path.resolve().as_posix()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    required = {
        row["name"]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    missing = set(TABLES) - required
    if missing:
        connection.close()
        raise RuntimeError(
            "SQLite snapshot thiếu bảng: " + ", ".join(sorted(missing))
        )
    return connection


def source_rows(
    connection: sqlite3.Connection, table: str
) -> tuple[list[str], list[tuple]]:
    columns = [
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table})")
    ]
    rows = [
        tuple(row[column] for column in columns)
        for row in connection.execute(f"SELECT * FROM {table}")
    ]
    return columns, rows


def counts(connection, tables=TABLES) -> dict[str, int]:
    return {
        table: int(scalar(connection.execute(f"SELECT COUNT(*) FROM {table}")))
        for table in tables
    }


def source_counts(connection: sqlite3.Connection) -> dict[str, int]:
    return {
        table: int(
            connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        )
        for table in TABLES
    }


def reset_identity(connection, table: str) -> None:
    connection.execute(
        f"""
        SELECT setval(
            pg_get_serial_sequence('{table}', 'id'),
            COALESCE((SELECT MAX(id) FROM {table}), 1),
            EXISTS (SELECT 1 FROM {table})
        )
        """
    )


def migrate(
    source: sqlite3.Connection,
    destination,
    *,
    replace: bool,
) -> tuple[dict[str, int], dict[str, int]]:
    before = counts(destination)
    if any(before.values()) and not replace:
        raise RuntimeError(
            "PostgreSQL đã có dữ liệu. Dùng --replace nếu muốn thay toàn bộ "
            "bằng snapshot SQLite."
        )

    expected = source_counts(source)
    with destination.transaction():
        # Serialize against the paper monitor for the whole import.
        destination.execute(
            "SELECT id FROM scan_lock WHERE id=1 FOR UPDATE"
        ).fetchone()

        if replace:
            for table in DELETE_ORDER:
                destination.execute(f"DELETE FROM {table}")

        for table in TABLES:
            columns, rows = source_rows(source, table)
            if not rows:
                continue
            names = ",".join(columns)
            placeholders = ",".join("?" for _ in columns)
            destination.executemany(
                f"INSERT INTO {table} ({names}) VALUES ({placeholders})",
                rows,
            )

        for table in IDENTITY_TABLES:
            reset_identity(destination, table)

        actual = counts(destination)
        if actual != expected:
            raise RuntimeError(
                "Đối soát thất bại: "
                f"SQLite={expected}, PostgreSQL={actual}. Đã rollback."
            )
        orphan_events = int(scalar(destination.execute(
            """
            SELECT COUNT(*)
            FROM paper_events AS event
            LEFT JOIN paper_trades AS trade ON trade.id = event.trade_id
            WHERE trade.id IS NULL
            """
        )))
        if orphan_events:
            raise RuntimeError(
                f"Có {orphan_events} paper event không còn trade. Đã rollback."
            )
        destination.execute(
            "UPDATE scan_lock SET locked_at=NULL, holder=NULL WHERE id=1"
        )
    return before, actual


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sqlite_path", type=Path)
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Thay toàn bộ dữ liệu trading hiện có trong PostgreSQL.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Chỉ kiểm tra SQLite và in số lượng, không kết nối PostgreSQL.",
    )
    args = parser.parse_args()

    source = open_source(args.sqlite_path)
    try:
        expected = source_counts(source)
        if args.dry_run:
            print(json.dumps(
                {"source": str(args.sqlite_path), "counts": expected},
                ensure_ascii=False,
                indent=2,
            ))
            return 0

        target = resolve_database_target()
        if not is_postgres_target(target):
            raise RuntimeError(
                "Không có PostgreSQL DATABASE_URL. Dừng để tránh ghi nhầm "
                "vào SQLite local."
            )
        destination = connect_database(target)
        try:
            before, after = migrate(
                source, destination, replace=args.replace
            )
        finally:
            destination.close()
    finally:
        source.close()

    print(json.dumps(
        {
            "status": "ok",
            "destination": "PostgreSQL",
            "before": before,
            "after": after,
        },
        ensure_ascii=False,
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
