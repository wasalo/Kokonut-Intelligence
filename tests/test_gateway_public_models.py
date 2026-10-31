"""Focused response-model contract tests for public Gateway summaries."""

from datetime import datetime, timezone

import pytest

from services.gateway.public_models import (
    PublicAttestationCounts,
    PublicCrispAssessment,
    PublicMetricCounts,
)


@pytest.mark.parametrize(
    ("metric_count", "latest_computed_at"),
    [
        (0, None),
        (1, datetime(2026, 10, 14, 12, 30, tzinfo=timezone.utc)),
    ],
)
def test_public_metric_counts_accepts_consistent_count_and_timestamp(
    metric_count: int, latest_computed_at: datetime | None
) -> None:
    result = PublicMetricCounts(
        metric_count=metric_count,
        latest_computed_at=latest_computed_at,
    )

    assert result.metric_count == metric_count
    assert result.latest_computed_at == latest_computed_at


@pytest.mark.parametrize(
    ("metric_count", "latest_computed_at"),
    [
        (0, datetime(2026, 10, 14, 12, 30, tzinfo=timezone.utc)),
        (1, None),
    ],
)
def test_public_metric_counts_rejects_inconsistent_count_and_timestamp(
    metric_count: int, latest_computed_at: datetime | None
) -> None:
    with pytest.raises(ValueError, match="latest_computed_at must match metric_count"):
        PublicMetricCounts(
            metric_count=metric_count,
            latest_computed_at=latest_computed_at,
        )


@pytest.mark.parametrize(
    ("total_attestations", "published_count"),
    [(0, 0), (2, 1), (1, 1)],
)
def test_public_attestation_counts_accepts_published_subset(
    total_attestations: int, published_count: int
) -> None:
    result = PublicAttestationCounts(
        total_attestations=total_attestations,
        published_count=published_count,
        latest_attestation=None,
    )

    assert result.total_attestations == total_attestations
    assert result.published_count == published_count


def test_public_attestation_counts_rejects_published_count_above_total() -> None:
    with pytest.raises(ValueError, match="published_count must not exceed total_attestations"):
        PublicAttestationCounts(
            total_attestations=1,
            published_count=2,
            latest_attestation=None,
        )


@pytest.mark.parametrize("level", [None, 0, 6])
def test_public_crisp_assessment_accepts_canonical_evidence_maturity_levels(level):
    result = PublicCrispAssessment(
        assessment_id="b0000000-0000-4000-8000-000000000001",
        location_id="a0000000-0000-4000-8000-000000000001",
        period_start="2026-01-01",
        period_end="2026-06-30",
        methodology_version="crisp-1",
        composite_score=82,
        rating="AA",
        confidence_level="high",
        evidence_maturity_level=level,
        score_computed_at=None,
        status="published",
    )

    assert result.evidence_maturity_level == level


@pytest.mark.parametrize("level", [-1, 7])
def test_public_crisp_assessment_rejects_noncanonical_evidence_maturity_levels(level):
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        PublicCrispAssessment(
            assessment_id="b0000000-0000-4000-8000-000000000001",
            location_id="a0000000-0000-4000-8000-000000000001",
            period_start="2026-01-01",
            period_end="2026-06-30",
            methodology_version="crisp-1",
            composite_score=82,
            rating="AA",
            confidence_level="high",
            evidence_maturity_level=level,
            score_computed_at=None,
            status="published",
        )
