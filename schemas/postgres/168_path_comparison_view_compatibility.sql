BEGIN;

DROP VIEW IF EXISTS v_backcast_path_comparison_summary;
CREATE VIEW v_backcast_path_comparison_summary AS
SELECT
    bpc.id AS comparison_id,
    bpc.location_id,
    bpc.comparison_name,
    array_length(bpc.narrative_ids, 1) AS path_count,
    bpc.winner_narrative_id,
    bpc.winner_score,
    bpc.rationale,
    bpc.compared_by,
    bpc.created_at,
    nt.title AS winner_title
FROM backcast_path_comparison bpc
LEFT JOIN threat_narrative nt ON nt.id = bpc.winner_narrative_id;

CREATE OR REPLACE VIEW v_backcast_path_comparison_integrity AS
SELECT
    bpc.id AS comparison_id,
    bpc.location_id,
    bpc.comparison_name,
    array_length(bpc.narrative_ids, 1) AS path_count,
    bpc.evaluation_status,
    bpc.score_completeness,
    bpc.scoring_version,
    bpc.evaluated_at,
    bpc.winner_narrative_id,
    bpc.winner_score,
    bpc.rationale,
    bpc.compared_by,
    bpc.created_at,
    bpc.updated_at,
    COALESCE(pm.premortem_path_count, 0) AS premortem_path_count,
    COALESCE(pm.verified_premortem_count, 0) AS verified_premortem_count,
    COALESCE(pm.verified_premortem_count, 0) = array_length(bpc.narrative_ids, 1)
        AS premortem_complete,
    nt.title AS winner_title
FROM backcast_path_comparison bpc
LEFT JOIN threat_narrative nt ON nt.id = bpc.winner_narrative_id
LEFT JOIN LATERAL (
    SELECT
        COUNT(DISTINCT p.narrative_id) AS premortem_path_count,
        COUNT(DISTINCT p.narrative_id) FILTER (WHERE p.status = 'verified')
            AS verified_premortem_count
    FROM backcast_path_premortem p
    WHERE p.comparison_id = bpc.id
) pm ON TRUE;

COMMIT;
