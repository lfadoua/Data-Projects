"""Run local quality checks with sanitized output; never changes .env or data.

Use --live to opt into the three read-only PostgreSQL tests. Provider generation
is mocked by unit tests and disabled in live tests using a process-only override.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from src.config.security import configured_secrets, redact_sensitive
from src.config.settings import PROJECT_ROOT


def run(output, live=False, tests=None):
    secrets = configured_secrets(PROJECT_ROOT / ".env")
    env = {**os.environ, "LLM_PROVIDER": "extractive", "RUN_DB_INTEGRATION": "1" if live else "0"}
    pytest_args = ["-m", "pytest", "-q", "--tb=short"]
    if not live:
        pytest_args += ["-m", "not live"]
    pytest_args += tests or []
    commands = [
        ("pytest", pytest_args),
        ("ruff", ["-m", "ruff", "check", "."]),
        ("format", ["-m", "ruff", "format", "--check", "."]),
    ]
    report = {"live_opt_in": live, "commands": []}
    output.parent.mkdir(parents=True, exist_ok=True)
    for name, args in commands:
        result = subprocess.run(
            [sys.executable, *args],
            cwd=PROJECT_ROOT,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        sanitized = redact_sensitive(result.stdout + result.stderr, secrets)
        report["commands"].append(
            {"name": name, "arguments": args, "returncode": result.returncode, "output": sanitized}
        )
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(name, result.returncode, sanitized[-1800:], flush=True)
    report["passed"] = all(c["returncode"] == 0 for c in report["commands"])
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("tests", nargs="*")
    args = parser.parse_args()
    result = run(args.output, args.live, args.tests)
    raise SystemExit(0 if result["passed"] else 1)
