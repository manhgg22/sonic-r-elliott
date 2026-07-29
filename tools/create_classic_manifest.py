"""Tạo manifest bất biến trước lần validation Sonic Classic chính thức."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from core.classic import SonicClassicConfig
from data.loader import _cache_path, fetch_ohlcv


ABLATIONS = [
    "require_leg1_cross:false_vs_true",
    "sl_max_adr:1.0_vs_none",
    "session_filter:none_vs_sonic_ny",
    "pivot_right:3_vs_5",
]
CODE_FILES = [
    "core/classic.py",
    "core/wave.py",
    "core/indicators.py",
    "backtest/engine.py",
    "run_backtest.py",
    "tools/measure_pva.py",
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", nargs="+", required=True)
    parser.add_argument("--days", type=int, required=True)
    parser.add_argument("--exchange", default="okx")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--funding-source",
        choices=["fallback_8h_assumption"],
        default="fallback_8h_assumption",
    )
    args = parser.parse_args()

    status = subprocess.run(
        ["git", "status", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if status:
        raise RuntimeError(
            "Chỉ tạo validation manifest sau khi code/data config đã commit sạch"
        )
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    files = []
    global_start = None
    global_end = None
    for symbol in args.symbols:
        frame = fetch_ohlcv(
            symbol,
            "15m",
            args.days,
            exchange_id=args.exchange,
            cache_max_age=None,
            verbose=False,
        )
        if frame.empty:
            raise RuntimeError(f"Không có OHLCV cho {symbol}")
        path = _cache_path(symbol, "15m", args.days, args.exchange)
        files.append({
            "symbol": symbol,
            "market_type": "linear_usdt_perpetual",
            "path": str(path.as_posix()),
            "size": path.stat().st_size,
            "sha256": _sha256(path),
            "min_timestamp": frame.index.min().isoformat(),
            "max_timestamp": frame.index.max().isoformat(),
        })
        global_start = (
            frame.index.min()
            if global_start is None else max(global_start, frame.index.min())
        )
        global_end = (
            frame.index.max()
            if global_end is None else min(global_end, frame.index.max())
        )

    manifest = {
        "schema_version": 1,
        "venue": args.exchange,
        "market_type": "linear_usdt_perpetual",
        "instruments": list(args.symbols),
        "start_utc": global_start.isoformat(),
        "end_utc": global_end.isoformat(),
        "timeframe": "15m",
        "requested_days": args.days,
        "warmup": "EMA89 H1 plus 14 positive-range D1 sessions",
        "missing_data_policy": "reject invalid OHLC; report gaps; no interpolation",
        "files": files,
        "funding_source": args.funding_source,
        "funding_rate_8h": 0.0001,
        "code_commit": commit,
        "code_files": [
            {
                "path": path,
                "sha256": _sha256(Path(path)),
            }
            for path in CODE_FILES
        ],
        "config": asdict(SonicClassicConfig()),
        "primary_tp_mode": "sr_level",
        "secondary_tp_modes": ["rdh_rdl", "fixed_r"],
        "ablations": ABLATIONS,
        "random_seed": 20260729,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Đã tạo manifest: {args.output}")


if __name__ == "__main__":
    main()
