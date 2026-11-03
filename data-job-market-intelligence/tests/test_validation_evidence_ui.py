"""Keep current evidence separate from the original release score, without services."""

import runpy
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import MagicMock

from app.components import dashboard, design, ui


def test_original_release_record_remains_historical():
    original = dashboard.validation_results()
    assert original["recorded_at"].startswith("2026-10-11")
    assert original["tests_passed"] == 61
    assert original["criteria_validated"] == 19
    assert original["criteria_total"] == 20
    assert original["docker_runtime_validated"] is False


def test_home_uses_current_tests_and_reports_docker_provenance(monkeypatch):
    fake = MagicMock()
    fake.columns.return_value = [nullcontext() for _ in range(4)]
    monkeypatch.setattr(dashboard, "st", fake)
    cards = MagicMock()
    monkeypatch.setattr(dashboard, "kpi", cards)
    current = dashboard.current_validation_results()
    dashboard.home_metrics({"total_jobs": 12217}, {"embeddings": 30955, "index_version": "v2"})
    assert cards.call_args_list[2].args[1] == current["tests_passed"]
    assert cards.call_args_list[3].args[:2] == ("Docker Runtime", "User verified")
    assert "reported" in cards.call_args_list[3].args[2]
    assert "progress" not in cards.call_args_list[3].kwargs


def test_validation_page_preserves_original_score_and_limits_new_claims(monkeypatch):
    fake = MagicMock()
    fake.columns.side_effect = lambda spec, **kwargs: [
        nullcontext() for _ in range(spec if isinstance(spec, int) else len(spec))
    ]
    import sys

    monkeypatch.setitem(sys.modules, "streamlit", fake)
    monkeypatch.setattr(ui, "setup", MagicMock())
    monkeypatch.setattr(ui, "read", lambda *args, **kwargs: None)
    monkeypatch.setattr(dashboard, "index_status", MagicMock())
    monkeypatch.setattr(design, "panel", lambda *args, **kwargs: nullcontext())
    monkeypatch.setattr(design, "kpi", MagicMock())
    runpy.run_path(str(Path(ui.ROOT) / "app/pages/4_Validation.py"))
    infos = " ".join(call.args[0] for call in fake.info.call_args_list)
    captions = " ".join(call.args[0] for call in fake.caption.call_args_list)
    assert "does not execute tests" in infos
    assert "user-verified" in infos
    assert "not been confirmed" in infos
    assert "retroactively change this score" in captions
    assert "Generative Docker execution is unverified" in captions
