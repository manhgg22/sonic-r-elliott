"""Create a consistent SQLite snapshot for PostgreSQL migration."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


TABLES = (
    "scan_runs",
    "latest_setups",
    "paper_trades",
    "paper_events",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("results/paper_trading.db"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/import/paper_trading.db"),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ghi đè snapshot cũ tại output.",
    )
    args = parser.parse_args()

    source_path = args.source.resolve()
    output_path = args.output.resolve()
    if not source_path.is_file():
        raise FileNotFoundError(f"Không tìm thấy database: {source_path}")
    if source_path == output_path:
        raise RuntimeError("Source và output không được trùng nhau.")
    if output_path.exists() and not args.force:
        raise FileExistsError(
            f"Snapshot đã tồn tại: {output_path}. Dùng --force để ghi đè."
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    source = sqlite3.connect(
        f"file:{source_path.as_posix()}?mode=ro",
        uri=True,
        timeout=30,
    )
    destination = sqlite3.connect(output_path)
    try:
        source.backup(destination)
        integrity = destination.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"SQLite integrity_check thất bại: {integrity}")
        counts = {
            table: int(
                destination.execute(
                    f"SELECT COUNT(*) FROM {table}"
                ).fetchone()[0]
            )
            for table in TABLES
        }
    finally:
        destination.close()
        source.close()

    print(json.dumps(
        {
            "status": "ok",
            "snapshot": str(output_path),
            "counts": counts,
        },
        ensure_ascii=False,
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
