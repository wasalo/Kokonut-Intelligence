"""Tests for the Pitch & Presentation service."""

import json

import pytest
import psycopg2

from services.ingestion.base import get_db
from services.analytics import pitch


def _db():
    try:
        return get_db()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no database available: {exc}")


def _location(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM location LIMIT 1")
        row = cur.fetchone()
    return str(row[0]) if row else None


def test_module_shape():
    assert hasattr(pitch, "get_templates")
    assert hasattr(pitch, "get_template")
    assert hasattr(pitch, "create_template")
    assert hasattr(pitch, "gather_evidence")
    assert hasattr(pitch, "generate_pitch")
    assert hasattr(pitch, "render_markdown")
    assert hasattr(pitch, "render_html")
    assert hasattr(pitch, "render_cli")
    assert hasattr(pitch, "render_pdf_ready")
    assert hasattr(pitch, "main")
    assert pitch.AUDIENCES == (
        "funders", "operators", "developers", "refi", "impact", "elevator"
    )


def test_create_and_list_templates():
    conn = _db()
    try:
        result = pitch.create_template(
            conn, "funders",
            hook="Test hook for funders",
            problem="Test problem statement",
            solution="Test solution description",
            proof_headline="Adelphi is live",
            cta_label="View data",
            cta_url="https://example.com",
            sections=[{"title": "Section 1", "content": "Content 1"}],
        )
        assert result["audience"] == "funders"
        templates = pitch.get_templates(conn)
        assert len(templates) >= 1
        funders = [t for t in templates if t["audience"] == "funders"]
        assert len(funders) == 1
    except psycopg2.ProgrammingError:
        pytest.skip("pitch_template table not present")
    finally:
        conn.close()


def test_get_template():
    conn = _db()
    try:
        pitch.create_template(
            conn, "developers",
            hook="Dev hook", problem="Dev problem",
            solution="Dev solution", proof_headline="700+ tables",
            cta_label="Repo", cta_url="https://github.com",
        )
        tmpl = pitch.get_template(conn, "developers")
        assert tmpl is not None
        assert tmpl["audience"] == "developers"
        assert tmpl["hook"] == "Dev hook"
    except psycopg2.ProgrammingError:
        pytest.skip("pitch_template table not present")
    finally:
        conn.close()


def test_create_template_invalid_audience():
    conn = _db()
    try:
        with pytest.raises(ValueError, match="audience must be one of"):
            pitch.create_template(
                conn, "invalid", hook="h", problem="p",
                solution="s", proof_headline="ph",
                cta_label="cl", cta_url="cu",
            )
    except psycopg2.ProgrammingError:
        pytest.skip("pitch_template table not present")
    finally:
        conn.close()


def test_gather_evidence():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location")
    try:
        evidence = pitch.gather_evidence(conn, loc)
        assert "farm" in evidence
        assert "crisp" in evidence
        assert "revenue" in evidence
        assert "harvests" in evidence
        assert "impact_claims" in evidence
        assert "attestations" in evidence
        assert "feedback" in evidence
        assert "carbon" in evidence
        assert "biodiversity" in evidence
    except psycopg2.ProgrammingError:
        pytest.skip("required tables not present")
    finally:
        conn.close()


def test_gather_evidence_no_location():
    conn = _db()
    try:
        fake_id = "00000000-0000-0000-0000-000000000000"
        evidence = pitch.gather_evidence(conn, fake_id)
        assert evidence["farm"] == {}
        assert evidence["harvests"] == []
    except psycopg2.ProgrammingError:
        pytest.skip("required tables not present")
    finally:
        conn.close()


def test_generate_pitch():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location")
    try:
        result = pitch.generate_pitch(conn, loc, "elevator")
        assert result["audience"] == "elevator"
        assert result["location_id"] == loc
        assert "hook" in result
        assert "problem" in result
        assert "solution" in result
        assert "metrics" in result
        assert "evidence" in result
        assert "generated_at" in result
    except psycopg2.ProgrammingError:
        pytest.skip("pitch_template table not present")
    finally:
        conn.close()


def test_generate_pitch_all_audiences():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location")
    try:
        for audience in pitch.AUDIENCES:
            result = pitch.generate_pitch(conn, loc, audience)
            assert result["audience"] == audience
            assert len(result["hook"]) > 0
            assert len(result["problem"]) > 0
            assert len(result["solution"]) > 0
    except psycopg2.ProgrammingError:
        pytest.skip("pitch_template table not present")
    finally:
        conn.close()


def test_render_markdown():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location")
    try:
        result = pitch.generate_pitch(conn, loc, "elevator")
        md = pitch.render_markdown(result)
        assert isinstance(md, str)
        assert "# Kokonut Network" in md
        assert "The Problem" in md
        assert "The Solution" in md
        assert "Live Proof" in md
    except psycopg2.ProgrammingError:
        pytest.skip("pitch_template table not present")
    finally:
        conn.close()


def test_render_html():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location")
    try:
        result = pitch.generate_pitch(conn, loc, "elevator")
        html = pitch.render_html(result)
        assert isinstance(html, str)
        assert "<!DOCTYPE html>" in html
        assert "Kokonut Network" in html
        assert "metrics-grid" in html or "The Problem" in html
    except psycopg2.ProgrammingError:
        pytest.skip("pitch_template table not present")
    finally:
        conn.close()


def test_render_cli():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location")
    try:
        result = pitch.generate_pitch(conn, loc, "elevator")
        cli = pitch.render_cli(result)
        assert isinstance(cli, str)
        assert "KOKONUT NETWORK" in cli
        assert "THE PROBLEM" in cli
        assert "THE SOLUTION" in cli
    except psycopg2.ProgrammingError:
        pytest.skip("pitch_template table not present")
    finally:
        conn.close()


def test_render_pdf_ready():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location")
    try:
        result = pitch.generate_pitch(conn, loc, "elevator")
        pdf = pitch.render_pdf_ready(result)
        assert isinstance(pdf, str)
        assert "<!DOCTYPE html>" in pdf
        assert "@media print" in pdf
    except psycopg2.ProgrammingError:
        pytest.skip("pitch_template table not present")
    finally:
        conn.close()


def test_pitch_metrics_populated():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location")
    try:
        result = pitch.generate_pitch(conn, loc, "elevator")
        metrics = result["metrics"]
        assert isinstance(metrics, dict)
        evidence = result["evidence"]
        assert isinstance(evidence["harvests"], list)
        assert isinstance(evidence["attestations"], list)
        assert isinstance(evidence["impact_claims"], list)
    except psycopg2.ProgrammingError:
        pytest.skip("pitch_template table not present")
    finally:
        conn.close()
