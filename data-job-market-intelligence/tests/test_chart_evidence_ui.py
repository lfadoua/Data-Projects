"""Charts must retain API counts while making the displayed units accessible."""

from contextlib import nullcontext
from unittest.mock import MagicMock

from app.components import charts


def test_heatmap_table_and_hover_preserve_api_evidence(monkeypatch):
    fake = MagicMock()
    fake.expander.return_value = nullcontext()
    monkeypatch.setattr(charts, "st", fake)
    charts.heatmap(
        [
            {"role": "Data Engineer", "skill": "Python", "count": 7},
            {"role": "Other / Unclassified", "skill": "SQL", "count": 3},
        ],
        ["Data Engineer", "Other / Unclassified"],
        ["Python", "SQL"],
    )
    figure = fake.plotly_chart.call_args.args[0]
    assert [list(row) for row in figure.data[0].z] == [[7, 0], [0, 3]]
    assert "postings" in figure.data[0].hovertemplate
    table = fake.dataframe.call_args.args[0]
    assert table.loc["Data Engineer", "Python"] == 7
    assert table.loc["Other / Unclassified", "SQL"] == 3


def test_skill_share_uses_filtered_total_and_escapes_source_labels(monkeypatch):
    fake = MagicMock()
    monkeypatch.setattr(charts, "st", fake)
    charts.skills_chart([{"name": "Python <script>", "count": 3}], total=8)
    html = fake.html.call_args.args[0]
    assert "37.50%" in html
    assert "3 postings" in html
    assert "&lt;script&gt;" in html
    assert "<script>" not in html
