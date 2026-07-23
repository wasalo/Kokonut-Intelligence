-- Data stream summary: chronological project posts, file attachments, and anchoring status.
SELECT
  l.name AS location,
  dsp.title,
  dsp.post_type,
  dsp.content_preview,
  dsp.author_id,
  dsp.status AS post_status,
  dsp.blockchain_anchored,
  dsp.chain,
  dsp.attestation_uid,
  dsp.created_at,
  (SELECT COUNT(*) FROM data_stream_post_file dspf WHERE dspf.post_id = dsp.id) AS file_count
FROM data_stream_post dsp
JOIN location l ON l.id = dsp.location_id
WHERE dsp.status IN ('verified', 'published')
ORDER BY dsp.created_at DESC;
