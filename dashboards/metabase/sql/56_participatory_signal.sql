SELECT experiment_name, signal_type, governance_scope, decision_binding,
  experiment_status, participation_rules, moderation_policy, safety_boundaries,
  evidence_maturity, evidence_maturity_label, public_summary
FROM v_public_participatory_signal_experiment
ORDER BY experiment_status, signal_type, experiment_name;
