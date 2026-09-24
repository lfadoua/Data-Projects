"""Boundary-aware matches using the versioned skill taxonomy."""

import json
import re
from functools import lru_cache
from pathlib import Path

from src.config.settings import PROJECT_ROOT


@lru_cache(maxsize=8)
def taxonomy(path: str = str(PROJECT_ROOT / "config/skills.json")) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))["skills"]


def _compile(dictionary: dict) -> tuple:
    return tuple(
        (
            name,
            tuple(
                re.compile(r"(?<![\w])" + re.escape(alias) + r"(?![\w])", re.I) for alias in aliases
            ),
        )
        for name, aliases in dictionary.items()
    )


@lru_cache(maxsize=1)
def _default_patterns() -> tuple:
    return _compile(taxonomy())


def extract_skills(text: str, dictionary: dict | None = None) -> list[str]:
    patterns = _default_patterns() if dictionary is None else _compile(dictionary)
    return sorted(
        name for name, aliases in patterns if any(pattern.search(text) for pattern in aliases)
    )
