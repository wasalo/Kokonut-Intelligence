"""Unit tests for Data Stream feature."""

import hashlib
import json
import uuid
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_conn(rows=None, rowcount=1):
    """Create a mock database connection with configurable return values."""
    conn = MagicMock()
    result = MagicMock()
    mappings = MagicMock()

    if rows is None:
        rows = []
    elif isinstance(rows, dict):
        rows = [rows]

    # Make mappings() iterable and support .all() and .first()
    mappings_result = MagicMock()
    mappings_result.all.return_value = rows
    mappings_result.first.return_value = rows[0] if rows else None
    mappings_result.__iter__ = lambda self: iter(rows)
    mappings.return_value = mappings_result

    result.mappings.return_value = mappings_result
    result.rowcount = rowcount
    conn.execute.return_value = result
    conn.text = lambda sql: sql
    return conn


LOCATION_ID = str(uuid.uuid4())
POST_ID = str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Post CRUD tests
# ---------------------------------------------------------------------------

class TestCreatePost:
    def test_create_post_basic(self):
        from services.data_stream.post import create_post
        conn = _fake_conn(rows={"id": POST_ID, "created_at": "2026-07-01"})
        result = create_post(conn, location_id=LOCATION_ID, title="Test Post")
        assert result["id"] == POST_ID

    def test_create_post_with_evidence(self):
        from services.data_stream.post import create_post
        conn = _fake_conn(rows={"id": POST_ID, "created_at": "2026-07-01"})
        result = create_post(
            conn,
            location_id=LOCATION_ID,
            title="Post with evidence",
            evidence_urls=["https://example.com/photo.jpg"],
        )
        assert result["id"] == POST_ID

    def test_create_post_with_files(self):
        from services.data_stream.post import create_post
        conn = _fake_conn(rows={"id": POST_ID, "created_at": "2026-07-01"})
        result = create_post(
            conn,
            location_id=LOCATION_ID,
            title="Post with files",
            file_ids=[str(uuid.uuid4())],
        )
        assert result["id"] == POST_ID

    def test_create_post_markdown_content(self):
        from services.data_stream.post import create_post, _compute_content_hash
        conn = _fake_conn(rows={"id": POST_ID, "created_at": "2026-07-01"})
        content = "# Heading\n\n**Bold text** and [link](https://example.com)"
        result = create_post(conn, location_id=LOCATION_ID, title="MD Post", content=content)
        assert result["id"] == POST_ID
        expected_hash = hashlib.sha256(content.encode()).hexdigest()
        call_kwargs = conn.execute.call_args
        assert call_kwargs is not None

    def test_create_post_invalid_type(self):
        from services.data_stream.post import create_post
        conn = _fake_conn()
        with pytest.raises(ValueError, match="Invalid post_type"):
            create_post(conn, location_id=LOCATION_ID, post_type="bad_type", title="X")

    def test_create_post_invalid_visibility(self):
        from services.data_stream.post import create_post
        conn = _fake_conn()
        with pytest.raises(ValueError, match="Invalid visibility"):
            create_post(conn, location_id=LOCATION_ID, visibility="secret", title="X")

    def test_create_post_missing_title(self):
        from services.data_stream.post import create_post
        conn = _fake_conn()
        with pytest.raises(ValueError, match="title is required"):
            create_post(conn, location_id=LOCATION_ID, title="")


class TestUpdatePost:
    def test_update_post(self):
        from services.data_stream.post import update_post
        conn = _fake_conn()
        result = update_post(conn, POST_ID, title="Updated Title")
        assert result["id"] == POST_ID
        assert "title" in result["updated_fields"]

    def test_update_post_invalid_type(self):
        from services.data_stream.post import update_post
        conn = _fake_conn()
        with pytest.raises(ValueError, match="Invalid post_type"):
            update_post(conn, POST_ID, post_type="bad")

    def test_update_post_no_fields(self):
        from services.data_stream.post import update_post
        conn = _fake_conn()
        with pytest.raises(ValueError, match="No valid fields"):
            update_post(conn, POST_ID)


class TestGetPost:
    def test_get_post_found(self):
        from services.data_stream.post import get_post
        conn = _fake_conn(rows={"id": POST_ID, "title": "Test"})
        post = get_post(conn, POST_ID)
        assert post["id"] == POST_ID

    def test_get_post_not_found(self):
        from services.data_stream.post import get_post
        conn = _fake_conn(rows=[])
        post = get_post(conn, POST_ID)
        assert post is None


class TestListPosts:
    def test_list_posts(self):
        from services.data_stream.post import list_posts_by_project
        conn = _fake_conn(rows=[{"id": POST_ID, "title": "P1"}, {"id": str(uuid.uuid4()), "title": "P2"}])
        posts = list_posts_by_project(conn, LOCATION_ID)
        assert len(posts) == 2


class TestSearchPosts:
    def test_search_posts(self):
        from services.data_stream.post import search_posts
        conn = _fake_conn(rows=[{"id": POST_ID, "title": "Soil moisture", "rank": 0.95}])
        results = search_posts(conn, "soil moisture")
        assert len(results) == 1
        assert results[0]["rank"] == 0.95


class TestDeletePost:
    def test_delete_post(self):
        from services.data_stream.post import delete_post
        conn = _fake_conn(rowcount=1)
        assert delete_post(conn, POST_ID) is True

    def test_delete_post_not_found(self):
        from services.data_stream.post import delete_post
        conn = _fake_conn(rowcount=0)
        assert delete_post(conn, POST_ID) is False


# ---------------------------------------------------------------------------
# Stream tests
# ---------------------------------------------------------------------------

class TestStream:
    def test_get_project_stream(self):
        from services.data_stream.stream import get_project_stream
        conn = _fake_conn(rows=[{"id": POST_ID, "title": "Stream post"}])
        posts = get_project_stream(conn, LOCATION_ID)
        assert len(posts) == 1

    def test_get_chronological_feed(self):
        from services.data_stream.stream import get_chronological_feed
        conn = _fake_conn(rows=[{"id": POST_ID}])
        feed = get_chronological_feed(conn)
        assert len(feed) == 1

    def test_get_filtered_stream(self):
        from services.data_stream.stream import get_filtered_stream
        conn = _fake_conn(rows=[{"id": POST_ID}])
        stream = get_filtered_stream(conn, LOCATION_ID, post_type="photo")
        assert len(stream) == 1


# ---------------------------------------------------------------------------
# Anchor tests
# ---------------------------------------------------------------------------

class TestAnchor:
    def test_anchor_post(self):
        from services.data_stream.anchor import anchor_post
        conn = _fake_conn(rows=[
            {"id": POST_ID, "location_id": LOCATION_ID, "post_type": "photo",
             "title": "Test", "content_hash": "abc123", "media_type": "image",
             "visibility": "public", "status": "published", "is_anchored": False, "attestation_uid": None},
            {"schema_uid": "0x123"},
            {"id": str(uuid.uuid4())},
        ])
        result = anchor_post(conn, POST_ID, chain="celo")
        assert result["chain"] == "celo"
        assert "content_payload_hash" in result

    def test_anchor_post_already_anchored(self):
        from services.data_stream.anchor import anchor_post
        conn = _fake_conn(rows=[{
            "id": POST_ID, "status": "published", "is_anchored": True, "attestation_uid": "0xexisting",
        }])
        result = anchor_post(conn, POST_ID)
        assert result["already_anchored"] is True

    def test_anchor_post_not_found(self):
        from services.data_stream.anchor import anchor_post
        conn = _fake_conn(rows=[])
        with pytest.raises(ValueError, match="not found"):
            anchor_post(conn, POST_ID)

    def test_anchor_post_wrong_status(self):
        from services.data_stream.anchor import anchor_post
        conn = _fake_conn(rows=[{"id": POST_ID, "status": "draft", "is_anchored": False}])
        with pytest.raises(ValueError, match="must be verified or published"):
            anchor_post(conn, POST_ID)

    def test_verify_post_anchoring(self):
        from services.data_stream.anchor import verify_post_anchoring
        conn = _fake_conn(rows=[{"id": POST_ID, "is_anchored": True, "attestation_uid": "0x123"}])
        result = verify_post_anchoring(conn, POST_ID)
        assert result["is_anchored"] is True

    def test_list_anchored_posts(self):
        from services.data_stream.anchor import list_anchored_posts
        conn = _fake_conn(rows=[{"id": POST_ID, "attestation_uid": "0x123"}])
        posts = list_anchored_posts(conn, LOCATION_ID)
        assert len(posts) == 1


# ---------------------------------------------------------------------------
# Content hash test
# ---------------------------------------------------------------------------

class TestContentHash:
    def test_compute_hash(self):
        from services.data_stream.post import _compute_content_hash
        h = _compute_content_hash("hello world")
        assert h == hashlib.sha256("hello world".encode()).hexdigest()

    def test_compute_hash_none(self):
        from services.data_stream.post import _compute_content_hash
        assert _compute_content_hash(None) is None

    def test_compute_hash_empty(self):
        from services.data_stream.post import _compute_content_hash
        assert _compute_content_hash("") == hashlib.sha256(b"").hexdigest()


# ---------------------------------------------------------------------------
# Safety tests
# ---------------------------------------------------------------------------

class TestSafety:
    def test_data_stream_post_in_governed(self):
        from services.agents.safety import GOVERNED_COLLECTIONS
        assert "data_stream_post" in GOVERNED_COLLECTIONS

    def test_data_stream_post_comment_in_governed(self):
        from services.agents.safety import GOVERNED_COLLECTIONS
        assert "data_stream_post_comment" in GOVERNED_COLLECTIONS

    def test_agent_cannot_publish(self):
        from services.agents.safety import assess_agent_action
        decision = assess_agent_action(
            "status_change_to_published",
            "data_stream_post",
            {"status": "published"},
        )
        assert decision.allowed is False


# ---------------------------------------------------------------------------
# EAS schema tests
# ---------------------------------------------------------------------------

class TestEASSchema:
    def test_data_post_schema_exists(self):
        from services.attestation.schemas import KOKONUT_SCHEMAS
        assert "kokonut-data-post" in KOKONUT_SCHEMAS

    def test_data_post_schema_db_name(self):
        from services.attestation.schemas import SCHEMA_DB_NAMES
        assert SCHEMA_DB_NAMES["kokonut-data-post"] == "Kokonut Data Post"

    def test_prepare_data_post_attestation(self):
        from services.attestation.schemas import prepare_data_post_attestation_data
        fields = prepare_data_post_attestation_data(
            location_id="loc1",
            post_type="photo",
            title="Test",
            content_hash="abc",
            media_type="image",
            timestamp=1234567890,
            visibility="public",
            evidence_hash="def",
            payload_cid="Qm123",
        )
        assert len(fields) == 9
        assert fields[0]["name"] == "locationId"


# ---------------------------------------------------------------------------
# Report generator test
# ---------------------------------------------------------------------------

class TestReportGenerator:
    def test_data_stream_summary_in_registry(self):
        from services.export.report_generator import REPORT_GENERATORS
        assert "data_stream_summary" in REPORT_GENERATORS

    def test_data_stream_summary_generator(self):
        from services.export.report_generator import generate_data_stream_summary
        conn = _fake_conn(rows=[
            {"post_type": "photo", "status": "published", "visibility": "public", "is_anchored": True, "created_at": "2026-07-01"},
            {"post_type": "field_update", "status": "draft", "visibility": "internal", "is_anchored": False, "created_at": "2026-07-02"},
        ])
        report = generate_data_stream_summary(conn, LOCATION_ID)
        assert report["report_type"] == "data_stream_summary"
        assert report["total_posts"] == 2
        assert report["anchored_posts"] == 1
        assert report["by_type"]["photo"] == 1


# ---------------------------------------------------------------------------
# Constraint tests
# ---------------------------------------------------------------------------

class TestConstraints:
    def test_valid_post_types(self):
        from services.data_stream.post import VALID_POST_TYPES
        assert "field_update" in VALID_POST_TYPES
        assert "monitoring_report" in VALID_POST_TYPES
        assert "photo" in VALID_POST_TYPES
        assert "satellite_image" in VALID_POST_TYPES
        assert "soil_analysis" in VALID_POST_TYPES
        assert "biodiversity_survey" in VALID_POST_TYPES
        assert "community_update" in VALID_POST_TYPES
        assert len(VALID_POST_TYPES) == 15

    def test_valid_visibility(self):
        from services.data_stream.post import VALID_VISIBILITY
        assert VALID_VISIBILITY == {"public", "internal", "private"}

    def test_valid_statuses(self):
        from services.data_stream.post import VALID_STATUSES
        assert VALID_STATUSES == {"draft", "submitted", "verified", "published", "rejected"}
