from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


BACKEND_DIR = Path(__file__).resolve().parents[1]


def run_layer(layer: str) -> int:
    if layer == "workflow":
        return subprocess.call([sys.executable, "scripts/smoke_test.py"], cwd=BACKEND_DIR)

    start_dir = "tests/unit" if layer == "unit" else "tests/integration"
    env = os.environ.copy()
    with TemporaryDirectory(prefix=f"lifesnap-{layer}-") as data_dir:
        env["LIFESNAP_DATA_DIR"] = str(Path(data_dir) / "data")
        return subprocess.call(
            [sys.executable, "-m", "unittest", "discover", "-s", start_dir, "-t", ".", "-v"],
            cwd=BACKEND_DIR,
            env=env,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run LifeSnap tests by layer.")
    parser.add_argument(
        "layer",
        choices=("unit", "integration", "workflow", "all"),
        default="all",
        nargs="?",
    )
    args = parser.parse_args()
    layers = ("unit", "integration", "workflow") if args.layer == "all" else (args.layer,)
    for layer in layers:
        print(f"==> {layer}")
        result = run_layer(layer)
        if result:
            return result
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
