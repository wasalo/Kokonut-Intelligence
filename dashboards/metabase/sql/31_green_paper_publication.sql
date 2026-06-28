-- Green Paper publication dashboard: review state, approvals, open questions, and publication proof metadata.
SELECT
  version,
  document_path,
  review_status,
  review_owner,
  target_publication_date,
  open_question_count,
  approval_record_count,
  publication_cid,
  publication_hash,
  published_at,
  evidence_maturity,
  evidence_maturity_label,
  public_summary
FROM v_public_green_paper_publication_status
ORDER BY target_publication_date DESC, version DESC;
