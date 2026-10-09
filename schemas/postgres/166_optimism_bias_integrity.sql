-- Align CRISP labels with the documented higher-is-riskier score direction.
-- Automated report generation now creates draft snapshots in application code;
-- existing snapshots retain their reviewed/published state.

UPDATE crisp_risk_assessment
SET rating = CASE
    WHEN composite_score < 20 THEN 'AAA'
    WHEN composite_score < 44 THEN 'AA'
    WHEN composite_score < 69 THEN 'A'
    WHEN composite_score < 80 THEN 'B'
    WHEN composite_score < 91 THEN 'C'
    ELSE 'D'
END
WHERE composite_score IS NOT NULL
  AND rating IS DISTINCT FROM CASE
      WHEN composite_score < 20 THEN 'AAA'
      WHEN composite_score < 44 THEN 'AA'
      WHEN composite_score < 69 THEN 'A'
      WHEN composite_score < 80 THEN 'B'
      WHEN composite_score < 91 THEN 'C'
      ELSE 'D'
  END;
