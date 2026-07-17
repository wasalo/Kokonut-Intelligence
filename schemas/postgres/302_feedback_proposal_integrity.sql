-- Keep automated feedback evaluation idempotent without rewriting outcome history.
WITH ranked AS (
    SELECT id,
           ROW_NUMBER() OVER (
               PARTITION BY source_outcome_id
               ORDER BY created_at DESC, id DESC
           ) AS row_number
    FROM feedback_loop
    WHERE status = 'proposed'
)
UPDATE feedback_loop fl
SET status = 'rejected',
    updated_at = NOW(),
    adjustment_reason = fl.adjustment_reason || ' [superseded duplicate proposal]'
FROM ranked r
WHERE fl.id = r.id
  AND r.row_number > 1;

CREATE UNIQUE INDEX IF NOT EXISTS idx_feedback_loop_one_proposal
    ON feedback_loop (source_outcome_id)
    WHERE status = 'proposed';
