"""Chart.js payload validation.

A malformed chart only surfaces as a blank canvas in the student's browser, so
these rules are the last place a mistake can be caught cheaply.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.models.enums import GraphType
from app.schemas.graph import ChartData, GraphCreate, validate_chart_for_type


def chart(**overrides) -> dict:
    base = {
        "labels": ["2023", "2024", "2025"],
        "datasets": [{"label": "Output", "data": [1.0, 2.0, 3.0]}],
    }
    return base | overrides


def test_accepts_a_well_formed_chart() -> None:
    parsed = ChartData.model_validate(chart())
    assert parsed.labels == ["2023", "2024", "2025"]
    assert parsed.datasets[0].data == [1.0, 2.0, 3.0]


def test_rejects_dataset_shorter_than_labels() -> None:
    with pytest.raises(PydanticValidationError, match="must match"):
        ChartData.model_validate(chart(datasets=[{"label": "Output", "data": [1.0, 2.0]}]))


def test_rejects_dataset_longer_than_labels() -> None:
    with pytest.raises(PydanticValidationError, match="must match"):
        ChartData.model_validate(
            chart(datasets=[{"label": "Output", "data": [1.0, 2.0, 3.0, 4.0]}])
        )


def test_names_the_offending_dataset() -> None:
    payload = chart(
        datasets=[
            {"label": "Good", "data": [1.0, 2.0, 3.0]},
            {"label": "Bad", "data": [1.0]},
        ]
    )
    with pytest.raises(PydanticValidationError, match="'Bad'"):
        ChartData.model_validate(payload)


def test_rejects_a_single_label() -> None:
    # One category is not a graph anyone can describe comparatively.
    with pytest.raises(PydanticValidationError):
        ChartData.model_validate({"labels": ["only"], "datasets": [{"label": "x", "data": [1.0]}]})


def test_rejects_no_datasets() -> None:
    with pytest.raises(PydanticValidationError):
        ChartData.model_validate(chart(datasets=[]))


def test_null_points_are_allowed() -> None:
    """A gap is drawn honestly rather than interpolated away."""
    parsed = ChartData.model_validate(chart(datasets=[{"label": "x", "data": [1.0, None, 3.0]}]))
    assert parsed.datasets[0].data[1] is None


def test_chart_js_styling_keys_survive() -> None:
    parsed = ChartData.model_validate(
        chart(datasets=[{"label": "x", "data": [1.0, 2.0, 3.0], "borderColor": "#7c3aed"}])
    )
    dumped = parsed.model_dump()
    assert dumped["datasets"][0]["borderColor"] == "#7c3aed"


def test_axis_labels_round_trip() -> None:
    parsed = ChartData.model_validate(chart(x_axis_label="Year", y_axis_label="MWh", unit="MWh"))
    assert parsed.y_axis_label == "MWh"


# ── Type-specific rules ──────────────────────────────────────────────────────


def test_pie_rejects_multiple_datasets() -> None:
    parsed = ChartData.model_validate(
        chart(
            datasets=[
                {"label": "a", "data": [1.0, 2.0, 3.0]},
                {"label": "b", "data": [4.0, 5.0, 6.0]},
            ]
        )
    )
    with pytest.raises(ValueError, match="exactly one dataset"):
        validate_chart_for_type(parsed, GraphType.PIE)


def test_pie_rejects_negative_values() -> None:
    parsed = ChartData.model_validate(chart(datasets=[{"label": "a", "data": [1.0, -2.0, 3.0]}]))
    with pytest.raises(ValueError, match="negative"):
        validate_chart_for_type(parsed, GraphType.PIE)


def test_pie_rejects_all_null_values() -> None:
    parsed = ChartData.model_validate(chart(datasets=[{"label": "a", "data": [None, None, None]}]))
    with pytest.raises(ValueError, match="non-null"):
        validate_chart_for_type(parsed, GraphType.PIE)


def test_bar_allows_multiple_datasets() -> None:
    parsed = ChartData.model_validate(
        chart(
            datasets=[
                {"label": "a", "data": [1.0, 2.0, 3.0]},
                {"label": "b", "data": [4.0, 5.0, 6.0]},
            ]
        )
    )
    validate_chart_for_type(parsed, GraphType.BAR)  # must not raise


def test_line_allows_negative_values() -> None:
    parsed = ChartData.model_validate(chart(datasets=[{"label": "a", "data": [-1.0, 0.0, 1.0]}]))
    validate_chart_for_type(parsed, GraphType.LINE)  # must not raise


def test_graph_create_applies_the_type_rule() -> None:
    """The rule fires through GraphCreate, not only when called directly."""
    with pytest.raises(PydanticValidationError, match="exactly one dataset"):
        GraphCreate.model_validate(
            {
                "title": "Two-series pie",
                "prompt": "Describe this chart in at least 150 words.",
                "graph_type": "pie",
                "chart_data": chart(
                    datasets=[
                        {"label": "a", "data": [1.0, 2.0, 3.0]},
                        {"label": "b", "data": [4.0, 5.0, 6.0]},
                    ]
                ),
            }
        )
