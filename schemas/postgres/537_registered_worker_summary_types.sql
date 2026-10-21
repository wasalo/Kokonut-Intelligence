-- Bound signed-worker draft creation to the summary types the Kernel worker runs.
-- NOT VALID preserves historical receipts while enforcing new inserts.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM pg_catalog.pg_constraint
         WHERE conname = 'ai_summary_agent_draft_request_registered_type_check'
           AND conrelid = 'public.ai_summary_agent_draft_request'::pg_catalog.regclass
    ) THEN
        ALTER TABLE public.ai_summary_agent_draft_request
            ADD CONSTRAINT ai_summary_agent_draft_request_registered_type_check
            CHECK (summary_type IN (
                'operations',
                'financial',
                'environmental',
                'combined',
                'bio_factory',
                'capital_efficiency',
                'commons_liberation',
                'stakeholder_feedback',
                'gnh_alignment',
                'holistic_wellbeing',
                'kokonut_commons',
                'open_source_capitalist',
                'financial_resilience',
                'regenerative_outcomes'
            )) NOT VALID;
    END IF;
END;
$$;

COMMENT ON CONSTRAINT ai_summary_agent_draft_request_registered_type_check
    ON public.ai_summary_agent_draft_request IS
    'Allows new signed-worker receipts only for the four deterministic and ten registered shared synthesis summary types; existing legacy receipts remain readable.';
