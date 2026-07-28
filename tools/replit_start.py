"""Run Sonic R as one Replit web process.

The supervisor exposes FastAPI on port 8000 and optionally keeps the paper
monitor alive. React is built during Replit's build phase and served by
FastAPI from frontend/dist.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_INDEX = ROOT / "frontend" / "dist" / "index.html"


def _enabled(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _start(command: list[str]) -> subprocess.Popen:
    return subprocess.Popen(command, cwd=ROOT)


def main() -> int:
    if not FRONTEND_INDEX.is_file():
        print(
            "frontend/dist chưa tồn tại. Chạy deployment build hoặc "
            "`npm ci --prefix frontend && npm run build --prefix frontend`.",
            file=sys.stderr,
        )
        return 2

    replit_runtime = bool(
        os.getenv("REPL_ID") or os.getenv("REPLIT_DEPLOYMENT")
    )
    monitor_enabled = _enabled("SONIC_RUN_MONITOR", replit_runtime)
    # .replit maps localPort 8000 to public port 80. Keep this explicit so a
    # platform-provided generic PORT value cannot desynchronise the mapping.
    port = os.getenv("SONIC_PORT", "8000")
    processes: list[subprocess.Popen] = []
    stopping = False

    def shutdown(_signum=None, _frame=None):
        nonlocal stopping
        if stopping:
            return
        stopping = True
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    server = _start([
        sys.executable,
        "-m",
        "uvicorn",
        "backend.app.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        port,
        "--proxy-headers",
        "--forwarded-allow-ips=*",
    ])
    processes.append(server)

    monitor: subprocess.Popen | None = None
    if monitor_enabled:
        monitor = _start([
            sys.executable,
            "paper_monitor.py",
            "--db",
            os.getenv("SONIC_DB_PATH", "results/paper_trading.db"),
        ])
        processes.append(monitor)
        print("Replit supervisor: web + paper monitor.")
    else:
        print("Replit supervisor: web only (SONIC_RUN_MONITOR=false).")

    try:
        while not stopping:
            server_code = server.poll()
            if server_code is not None:
                return server_code
            if monitor is not None and monitor.poll() is not None:
                print(
                    "Paper monitor đã dừng; khởi động lại sau 5 giây.",
                    file=sys.stderr,
                )
                time.sleep(5)
                monitor = _start([
                    sys.executable,
                    "paper_monitor.py",
                    "--db",
                    os.getenv(
                        "SONIC_DB_PATH", "results/paper_trading.db"
                    ),
                ])
                processes[-1] = monitor
            time.sleep(1)
    finally:
        shutdown()
        for process in reversed(processes):
            if process.poll() is None:
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
