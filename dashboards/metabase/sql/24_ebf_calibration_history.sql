SELECT
    session_name,
    location_name,
    session_date,
    rubric_version,
    calibration_frequency,
    calibration_method,
    status,
    decision_count,
    verified_decision_count,
    report_url
FROM v_ebf_calibration_history
ORDER BY session_date DESC, session_name;
