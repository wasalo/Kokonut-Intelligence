-- Minimal transactional fixture for migration 441 acceptance after migrations 437–440.
CREATE TABLE public.governance_tactical_session (
    id UUID PRIMARY KEY,
    circle_id UUID NOT NULL REFERENCES public.governance_circle(id),
    status TEXT NOT NULL CHECK (status IN ('planned', 'active', 'completed', 'cancelled')),
    outcome_summary TEXT,
    CHECK (status <> 'completed' OR NULLIF(BTRIM(outcome_summary), '') IS NOT NULL)
);
CREATE TABLE public.governance_tactical_item (
    id UUID PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES public.governance_tactical_session(id),
    owner_role_id UUID REFERENCES public.governance_role(id),
    owner_party_id UUID REFERENCES public.party(id),
    requested_next_action TEXT NOT NULL DEFAULT 'Review the assigned action.',
    status TEXT NOT NULL CHECK (status IN ('open', 'in_progress', 'disposed', 'cancelled')),
    disposition_type TEXT,
    disposition_summary TEXT,
    disposed_by_party_id UUID REFERENCES public.party(id),
    disposed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CHECK (owner_role_id IS NOT NULL OR owner_party_id IS NOT NULL OR status IN ('open', 'cancelled')),
    CHECK (status <> 'disposed' OR disposition_type IS NOT NULL),
    CHECK (status <> 'disposed' OR NULLIF(BTRIM(disposition_summary), '') IS NOT NULL),
    CHECK (status <> 'disposed' OR disposed_at IS NOT NULL)
);
GRANT SELECT, INSERT, UPDATE, DELETE ON public.governance_tactical_item
    TO kokonut_runtime, kokonut_directus_runtime;
INSERT INTO public.governance_tactical_session VALUES
    ('a0000000-0000-4000-8000-000000000901', 'a0000000-0000-4000-8000-000000000801', 'active', NULL),
    ('a0000000-0000-4000-8000-000000000902', 'a0000000-0000-4000-8000-000000000801', 'completed', 'Synthetic session completed with actions still in progress.');
INSERT INTO public.governance_role (id, circle_id, role_key, name, status) VALUES
    ('a0000000-0000-4000-8000-000000000813', 'a0000000-0000-4000-8000-000000000801', 'tactical_owner', 'Tactical Owner', 'active');
INSERT INTO public.governance_role_assignment (
    id, role_id, party_id, assignment_type, status, assigned_by_party_id,
    approved_by_party_id, recusal_status, effective_from
) VALUES (
    'a0000000-0000-4000-8000-000000000821',
    'a0000000-0000-4000-8000-000000000813',
    'a0000000-0000-4000-8000-000000000501',
    'primary', 'active', 'a0000000-0000-4000-8000-000000000502',
    'a0000000-0000-4000-8000-000000000502', 'clear', clock_timestamp() - INTERVAL '1 day'
);
INSERT INTO public.governance_role_assignment (
    id, role_id, party_id, assignment_type, status, assigned_by_party_id,
    approved_by_party_id, recusal_status, effective_from
) VALUES (
    'a0000000-0000-4000-8000-000000000822',
    'a0000000-0000-4000-8000-000000000812',
    'a0000000-0000-4000-8000-000000000501',
    'primary', 'active', 'a0000000-0000-4000-8000-000000000502',
    'a0000000-0000-4000-8000-000000000502', 'clear', clock_timestamp() - INTERVAL '1 day'
);
INSERT INTO public.governance_tactical_item (id, session_id, owner_party_id, owner_role_id, status) VALUES
    ('a0000000-0000-4000-8000-000000000911', 'a0000000-0000-4000-8000-000000000901', 'a0000000-0000-4000-8000-000000000501', NULL, 'open'),
    ('a0000000-0000-4000-8000-000000000912', 'a0000000-0000-4000-8000-000000000901', 'a0000000-0000-4000-8000-000000000502', NULL, 'open'),
    ('a0000000-0000-4000-8000-000000000913', 'a0000000-0000-4000-8000-000000000901', 'a0000000-0000-4000-8000-000000000501', NULL, 'open'),
    ('a0000000-0000-4000-8000-000000000914', 'a0000000-0000-4000-8000-000000000901', NULL, 'a0000000-0000-4000-8000-000000000813', 'open'),
    ('a0000000-0000-4000-8000-000000000915', 'a0000000-0000-4000-8000-000000000902', NULL, 'a0000000-0000-4000-8000-000000000813', 'open'),
    ('a0000000-0000-4000-8000-000000000916', 'a0000000-0000-4000-8000-000000000902', NULL, 'a0000000-0000-4000-8000-000000000812', 'open');
