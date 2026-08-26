"""Start the FastAPI service (port 5000) and the Vite widget together.

From the repo root:

    python scripts/dev.py
"""

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT / "frontend" / "ChatbotUI"
API_PORT = 5000


def _fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)


def _stop(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def main() -> int:
    if not (FRONTEND_DIR / "package.json").is_file():
        _fail(f"Frontend package.json not found in {FRONTEND_DIR}")
    if not (FRONTEND_DIR / "node_modules").is_dir():
        _fail("Frontend dependencies are missing. In frontend/ChatbotUI run:\n  npm install")

    npm = shutil.which("npm")
    if not npm:
        _fail("npm was not found on PATH. Install Node.js, then retry.")

    ui_env = os.environ.copy()
    ui_env["VITE_API_BASE_URL"] = f"http://localhost:{API_PORT}"

    print(f"API  http://localhost:{API_PORT}")
    print("UI   Vite prints its URL below")
    print("Ctrl+C stops both.\n")

    api = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "src.api.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            str(API_PORT),
        ],
        cwd=ROOT,
    )
    ui = subprocess.Popen([npm, "run", "dev"], cwd=FRONTEND_DIR, env=ui_env)
    procs = (api, ui)
    status = 0

    try:
        while True:
            for proc, name in ((api, "API"), (ui, "UI")):
                code = proc.poll()
                if code is None:
                    continue
                print(
                    f"\n{name} exited with code {code}. Stopping the other process.",
                    file=sys.stderr,
                )
                status = code if code != 0 else 1
                return status
            time.sleep(0.25)
    except KeyboardInterrupt:
        print("\nStopping API and UI...")
        return 0
    finally:
        for proc in procs:
            _stop(proc)


if __name__ == "__main__":
    raise SystemExit(main())
