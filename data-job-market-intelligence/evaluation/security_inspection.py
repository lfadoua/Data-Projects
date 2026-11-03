"""Inspect current files and local diagnostics without returning secret values.

This is a bounded inspection, not a full history or all-secret certification.
"""

import argparse
import json
import re
import subprocess
from pathlib import Path

from dotenv import dotenv_values

from src.config.security import SECRET_KEYS, configured_secrets
from src.config.settings import PROJECT_ROOT

_CREDENTIAL_URI = re.compile(r"postgres(?:ql)?(?:\+\w+)?://[^\s:/]+:[^\s/@]+@[^\s\"'<>]+")
_API_TOKEN = re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b")


def inspect(output):
    root, repository = PROJECT_ROOT, PROJECT_ROOT.parent
    secrets = configured_secrets(root / ".env")
    inventory = (
        subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=repository
        )
        .decode()
        .split("\0")
    )
    files = {repository / n for n in inventory if n and (repository / n).is_file()}
    for directory in (root / "evaluation/results", root / "data/models"):
        files.update(
            f
            for f in directory.rglob("*")
            if f.is_file()
            and f.suffix.lower() in {".json", ".log", ".md", ".txt", ".py"}
            and "__pycache__" not in f.parts
        )
    findings, skipped, scanned = [], [], 0
    for file in sorted(files):
        if file.stat().st_size > 5_000_000:
            skipped.append(str(file.relative_to(repository)))
            continue
        try:
            text = file.read_text(encoding="utf-8")
        except (UnicodeError, OSError):
            continue
        scanned += 1
        reasons = []
        if any(secret in text for secret in secrets):
            reasons.append("configured credential literal or encoded value")
        for match in _CREDENTIAL_URI.finditer(text):
            # Only explicitly synthetic test fixtures use this reserved domain.
            if "example.invalid" not in match.group() or "dummy-" not in match.group():
                reasons.append("credential-bearing PostgreSQL URI pattern")
        if _API_TOKEN.search(text):
            reasons.append("API token pattern")
        if reasons:
            findings.append({"file": str(file.relative_to(repository)), "reasons": reasons})
    example = dotenv_values(root / ".env.example", interpolate=False)
    placeholders = {
        key: not value or value in {"change-me", "replace-me", "your-api-key", "your-admin-token"}
        for key in SECRET_KEYS
        if (value := example.get(key)) is not None
    }
    report = {
        "text_files_scanned": scanned,
        "findings": findings,
        "large_files_skipped": skipped,
        "env_ignored": subprocess.run(
            ["git", "check-ignore", "-q", ".env"], cwd=root, check=False
        ).returncode
        == 0,
        "env_tracked": bool(
            subprocess.check_output(["git", "ls-files", "--", ".env"], cwd=root).strip()
        ),
        "env_example_secret_placeholders": placeholders,
        "scope": (
            "Current tracked/nonignored text plus local logs/reports: configured literal and "
            "URL-encoded secrets, credential-bearing PostgreSQL URIs and API token patterns. "
            "No full Git history, screenshot, terminal history or external-service inspection."
        ),
        "manual_rotation_status": "Not performed by agent; user action still required",
    }
    report["passed"] = (
        not findings
        and report["env_ignored"]
        and not report["env_tracked"]
        and all(placeholders.values())
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = inspect(args.output)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    raise SystemExit(0 if result["passed"] else 1)
