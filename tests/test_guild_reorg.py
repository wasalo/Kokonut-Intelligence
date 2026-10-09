"""Regression checks for durable Guild projection reorg recovery."""

from pathlib import Path


MIGRATION = Path("schemas/postgres/323_guild_projection_reorg_recovery.sql")
INDEXER = Path("services/guilds/indexer.py")
PROJECTIONS = Path("services/guilds/projections.py")


def test_reorg_migration_tracks_chain_owned_projection_provenance() -> None:
    text = MIGRATION.read_text()
    for table in [
        "kokonut_guild",
        "guild_domain",
        "guild_task",
        "guild_evidence_review",
        "guild_motion",
        "guild_reputation_event",
        "kgp_claim",
    ]:
        assert f"ALTER TABLE {table}" in text
        assert "source_chain_event_id UUID REFERENCES kgp_chain_event(id)" in text
    assert "is_canonical BOOLEAN NOT NULL DEFAULT TRUE" in text
    assert "ON DELETE SET NULL" in text


def test_reorg_recovery_resets_and_replays_canonical_events() -> None:
    indexer = INDEXER.read_text()
    projections = PROJECTIONS.read_text()
    assert "reset_chain_projections(cursor, self.deployment_id)" in indexer
    assert "self._replay_canonical_events(cursor)" in indexer
    assert "ORDER BY block_number, log_index" in indexer
    assert "def reset_chain_projections" in projections
    assert "chain_projection = TRUE" in projections
