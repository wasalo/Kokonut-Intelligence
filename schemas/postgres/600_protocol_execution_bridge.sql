-- Governed bridge between KI-approved intents and Protocol destination evidence.
-- KI remains canonical; this migration only adds explicit request/reconciliation records.

BEGIN;

CREATE TABLE IF NOT EXISTS public.protocol_project_location (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    protocol_project_id UUID NOT NULL,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    status VARCHAR(16) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'active', 'revoked')),
    mapped_by_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    approved_by_party_id UUID REFERENCES public.party(id) ON DELETE RESTRICT,
    approved_at TIMESTAMPTZ,
    revoked_by_party_id UUID REFERENCES public.party(id) ON DELETE RESTRICT,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (
        (status = 'draft' AND approved_by_party_id IS NULL AND approved_at IS NULL
            AND revoked_by_party_id IS NULL AND revoked_at IS NULL)
        OR (status = 'active' AND approved_by_party_id IS NOT NULL AND approved_at IS NOT NULL
            AND revoked_by_party_id IS NULL AND revoked_at IS NULL)
        OR (status = 'revoked' AND approved_by_party_id IS NOT NULL AND approved_at IS NOT NULL
            AND revoked_by_party_id IS NOT NULL AND revoked_at IS NOT NULL)
    )
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_protocol_project_location_active
    ON public.protocol_project_location(protocol_project_id) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_protocol_project_location_location
    ON public.protocol_project_location(location_id, status);

CREATE TABLE IF NOT EXISTS public.protocol_execution_intent (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID NOT NULL UNIQUE,
    mapping_id UUID NOT NULL REFERENCES public.protocol_project_location(id) ON DELETE RESTRICT,
    request_payload JSONB NOT NULL CHECK (jsonb_typeof(request_payload) = 'object'),
    request_hash VARCHAR(66) NOT NULL CHECK (request_hash ~ '^0x[0-9a-f]{64}$'),
    approval_threshold SMALLINT NOT NULL CHECK (approval_threshold > 0),
    requested_by_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    status VARCHAR(16) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'approved')),
    submitted_at TIMESTAMPTZ,
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (COALESCE(request_payload->>'request_id' = request_id::text, FALSE)),
    CHECK (COALESCE(request_payload->>'protocol_version' = '1', FALSE)),
    CHECK (COALESCE(request_payload->>'chain_namespace' = 'eip155', FALSE)),
    CHECK (COALESCE(request_payload->>'chain_id' IN ('84532', '10200'), FALSE)),
    CHECK (COALESCE(request_payload->>'expected_effect_hash' ~ '^0x[0-9a-fA-F]{64}$', FALSE)),
    CHECK ((status = 'draft' AND submitted_at IS NULL AND approved_at IS NULL)
        OR (status = 'submitted' AND submitted_at IS NOT NULL AND approved_at IS NULL)
        OR (status = 'approved' AND submitted_at IS NOT NULL AND approved_at IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS idx_protocol_execution_intent_status
    ON public.protocol_execution_intent(status, created_at);

CREATE TABLE IF NOT EXISTS public.protocol_execution_outbox (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    intent_id UUID NOT NULL UNIQUE REFERENCES public.protocol_execution_intent(id) ON DELETE RESTRICT,
    payload JSONB NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    payload_hash VARCHAR(66) NOT NULL CHECK (payload_hash ~ '^0x[0-9a-f]{64}$'),
    delivery_status VARCHAR(16) NOT NULL DEFAULT 'ready'
        CHECK (delivery_status IN ('ready', 'dispatched', 'failed')),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    dispatched_at TIMESTAMPTZ,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK ((delivery_status = 'dispatched' AND dispatched_at IS NOT NULL)
        OR (delivery_status <> 'dispatched' AND dispatched_at IS NULL))
);
CREATE INDEX IF NOT EXISTS idx_protocol_execution_outbox_ready
    ON public.protocol_execution_outbox(created_at) WHERE delivery_status = 'ready';

CREATE TABLE IF NOT EXISTS public.protocol_execution_reconciliation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    intent_id UUID NOT NULL UNIQUE REFERENCES public.protocol_execution_intent(id) ON DELETE RESTRICT,
    chain_id NUMERIC(78, 0) NOT NULL CHECK (chain_id IN (84532, 10200)),
    transaction_hash VARCHAR(66) NOT NULL CHECK (transaction_hash ~ '^0x[0-9a-fA-F]{64}$'),
    receipt_block_number NUMERIC(78, 0) NOT NULL CHECK (receipt_block_number >= 0),
    receipt_block_hash VARCHAR(66) NOT NULL CHECK (receipt_block_hash ~ '^0x[0-9a-fA-F]{64}$'),
    expected_effect_hash VARCHAR(66) NOT NULL CHECK (expected_effect_hash ~ '^0x[0-9a-fA-F]{64}$'),
    observed_effect_hash VARCHAR(66) NOT NULL CHECK (observed_effect_hash ~ '^0x[0-9a-fA-F]{64}$'),
    finality_status VARCHAR(16) NOT NULL CHECK (finality_status = 'finalized'),
    evidence JSONB NOT NULL CHECK (jsonb_typeof(evidence) = 'object'),
    review_status VARCHAR(16) NOT NULL DEFAULT 'submitted'
        CHECK (review_status IN ('submitted', 'verified', 'rejected')),
    reviewed_by_party_id UUID REFERENCES public.party(id) ON DELETE RESTRICT,
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (lower(expected_effect_hash) = lower(observed_effect_hash)),
    CHECK ((review_status = 'submitted' AND reviewed_by_party_id IS NULL AND reviewed_at IS NULL)
        OR (review_status IN ('verified', 'rejected') AND reviewed_by_party_id IS NOT NULL AND reviewed_at IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS idx_protocol_execution_reconciliation_review
    ON public.protocol_execution_reconciliation(review_status, created_at);

CREATE UNIQUE INDEX IF NOT EXISTS uq_protocol_execution_human_approval
    ON public.approval(collection, record_id, approver_id, action)
    WHERE collection = 'protocol_execution_intent' AND action = 'approve';

CREATE OR REPLACE FUNCTION public.guard_protocol_project_location()
RETURNS TRIGGER LANGUAGE plpgsql SET search_path = pg_catalog AS $$
DECLARE
    mapper_type TEXT;
    approver_type TEXT;
    revoker_type TEXT;
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.status <> 'draft' THEN
            RAISE EXCEPTION 'project crosswalks must start in draft';
        END IF;
        SELECT party_type INTO mapper_type FROM public.party WHERE id = NEW.mapped_by_party_id;
        IF mapper_type IS DISTINCT FROM 'person' THEN
            RAISE EXCEPTION 'crosswalk mapper must be an identified human party' USING ERRCODE = '42501';
        END IF;
        RETURN NEW;
    END IF;
    IF OLD.status = 'draft' AND NEW.status = 'active' THEN
        IF NEW.protocol_project_id IS DISTINCT FROM OLD.protocol_project_id
           OR NEW.location_id IS DISTINCT FROM OLD.location_id
           OR NEW.mapped_by_party_id IS DISTINCT FROM OLD.mapped_by_party_id
           OR NEW.approved_by_party_id IS NULL
           OR NEW.approved_by_party_id = NEW.mapped_by_party_id
           OR NEW.approved_at IS NULL THEN
            RAISE EXCEPTION 'activation requires an unchanged mapping and a distinct human approver';
        END IF;
        SELECT party_type INTO approver_type FROM public.party WHERE id = NEW.approved_by_party_id;
        IF approver_type IS DISTINCT FROM 'person' THEN
            RAISE EXCEPTION 'crosswalk approver must be an identified human party' USING ERRCODE = '42501';
        END IF;
        RETURN NEW;
    ELSIF OLD.status = 'active' AND NEW.status = 'revoked' THEN
        IF NEW.protocol_project_id IS DISTINCT FROM OLD.protocol_project_id
           OR NEW.location_id IS DISTINCT FROM OLD.location_id
           OR NEW.mapped_by_party_id IS DISTINCT FROM OLD.mapped_by_party_id
           OR NEW.approved_by_party_id IS DISTINCT FROM OLD.approved_by_party_id
           OR NEW.approved_at IS DISTINCT FROM OLD.approved_at
           OR NEW.revoked_by_party_id IS NULL OR NEW.revoked_at IS NULL THEN
            RAISE EXCEPTION 'revocation requires an unchanged mapping and identified human actor';
        END IF;
        SELECT party_type INTO revoker_type FROM public.party WHERE id = NEW.revoked_by_party_id;
        IF revoker_type IS DISTINCT FROM 'person' THEN
            RAISE EXCEPTION 'crosswalk revoker must be an identified human party' USING ERRCODE = '42501';
        END IF;
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'invalid project crosswalk transition: % -> %', OLD.status, NEW.status;
END;
$$;
CREATE TRIGGER trg_protocol_project_location_guard
    BEFORE INSERT OR UPDATE ON public.protocol_project_location
    FOR EACH ROW EXECUTE FUNCTION public.guard_protocol_project_location();

CREATE OR REPLACE FUNCTION public.guard_protocol_execution_intent()
RETURNS TRIGGER LANGUAGE plpgsql SET search_path = pg_catalog AS $$
DECLARE
    mapping public.protocol_project_location%ROWTYPE;
    requester_type TEXT;
    approvals INTEGER;
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.status <> 'draft' THEN
            RAISE EXCEPTION 'execution intents must start in draft';
        END IF;
        SELECT * INTO mapping FROM public.protocol_project_location WHERE id = NEW.mapping_id;
        IF mapping.id IS NULL OR mapping.status <> 'active'
           OR NEW.request_payload->>'project_id' IS DISTINCT FROM mapping.protocol_project_id::text
           OR NEW.request_payload->>'expires_at' IS NULL
           OR (NEW.request_payload->>'expires_at')::timestamptz <= NOW() THEN
            RAISE EXCEPTION 'execution intent project must match an active KI crosswalk';
        END IF;
        SELECT party_type INTO requester_type FROM public.party WHERE id = NEW.requested_by_party_id;
        IF requester_type IS DISTINCT FROM 'person' THEN
            RAISE EXCEPTION 'execution intent requester must be an identified human party' USING ERRCODE = '42501';
        END IF;
        RETURN NEW;
    END IF;
    IF NEW.id IS DISTINCT FROM OLD.id OR NEW.request_id IS DISTINCT FROM OLD.request_id
       OR NEW.mapping_id IS DISTINCT FROM OLD.mapping_id
       OR NEW.request_payload IS DISTINCT FROM OLD.request_payload
       OR NEW.request_hash IS DISTINCT FROM OLD.request_hash
       OR NEW.approval_threshold IS DISTINCT FROM OLD.approval_threshold
       OR NEW.requested_by_party_id IS DISTINCT FROM OLD.requested_by_party_id THEN
        RAISE EXCEPTION 'execution request snapshot is immutable';
    END IF;
    IF OLD.status = 'draft' AND NEW.status = 'submitted' AND NEW.submitted_at IS NOT NULL THEN
        RETURN NEW;
    ELSIF OLD.status = 'submitted' AND NEW.status = 'approved' AND NEW.approved_at IS NOT NULL THEN
        SELECT count(DISTINCT a.approver_id) INTO approvals
          FROM public.approval AS a
          JOIN public.party AS p ON p.id = a.approver_id AND p.party_type = 'person'
         WHERE a.collection = 'protocol_execution_intent'
           AND a.record_id = OLD.id AND a.action = 'approve'
           AND a.approver_id <> OLD.requested_by_party_id;
        IF approvals < OLD.approval_threshold OR NOT EXISTS (
            SELECT 1 FROM public.protocol_execution_outbox o
            WHERE o.intent_id = OLD.id AND o.delivery_status = 'ready'
        ) THEN
            RAISE EXCEPTION 'approval quorum and durable outbox are required before approval';
        END IF;
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'invalid execution intent transition: % -> %', OLD.status, NEW.status;
END;
$$;
CREATE TRIGGER trg_protocol_execution_intent_guard
    BEFORE INSERT OR UPDATE ON public.protocol_execution_intent
    FOR EACH ROW EXECUTE FUNCTION public.guard_protocol_execution_intent();

CREATE OR REPLACE FUNCTION public.guard_protocol_execution_approval()
RETURNS TRIGGER LANGUAGE plpgsql SET search_path = pg_catalog AS $$
DECLARE
    intent public.protocol_execution_intent%ROWTYPE;
    actor_type TEXT;
BEGIN
    IF TG_OP IN ('UPDATE', 'DELETE') THEN
        IF OLD.collection = 'protocol_execution_intent' AND OLD.action = 'approve' THEN
            RAISE EXCEPTION 'Protocol execution approval records are immutable';
        END IF;
        IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
    END IF;
    IF NEW.collection = 'protocol_execution_intent' AND NEW.action = 'approve' THEN
        SELECT * INTO intent FROM public.protocol_execution_intent WHERE id = NEW.record_id;
        IF intent.id IS NULL OR intent.status <> 'submitted'
           OR intent.requested_by_party_id = NEW.approver_id THEN
            RAISE EXCEPTION 'only a distinct human may approve a submitted execution intent';
        END IF;
        SELECT party_type INTO actor_type FROM public.party WHERE id = NEW.approver_id;
        IF actor_type IS DISTINCT FROM 'person' THEN
            RAISE EXCEPTION 'execution intent approver must be an identified human party' USING ERRCODE = '42501';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER trg_protocol_execution_approval_guard
    BEFORE INSERT OR UPDATE OR DELETE ON public.approval
    FOR EACH ROW EXECUTE FUNCTION public.guard_protocol_execution_approval();

CREATE OR REPLACE FUNCTION public.guard_protocol_execution_outbox()
RETURNS TRIGGER LANGUAGE plpgsql SET search_path = pg_catalog AS $$
DECLARE
    intent public.protocol_execution_intent%ROWTYPE;
    crosswalk public.protocol_project_location%ROWTYPE;
    approvals INTEGER;
    voter_ids JSONB;
BEGIN
    IF TG_OP = 'INSERT' THEN
        SELECT * INTO intent FROM public.protocol_execution_intent WHERE id = NEW.intent_id;
        IF intent.id IS NULL OR intent.status <> 'submitted'
           OR NEW.payload->>'request_id' IS DISTINCT FROM intent.request_id::text
           OR NEW.payload->>'intent_id' IS DISTINCT FROM intent.id::text
           OR NEW.payload->>'request_hash' IS DISTINCT FROM intent.request_hash
           OR NEW.payload->'request' IS DISTINCT FROM intent.request_payload THEN
            RAISE EXCEPTION 'outbox requires the matching submitted execution intent';
        END IF;
        SELECT count(*), COALESCE(jsonb_agg(to_jsonb(v.approver_id) ORDER BY v.approver_id), '[]'::jsonb)
          INTO approvals, voter_ids
          FROM (
              SELECT DISTINCT a.approver_id::text AS approver_id
                FROM public.approval a
                JOIN public.party p ON p.id = a.approver_id AND p.party_type = 'person'
               WHERE a.collection = 'protocol_execution_intent' AND a.record_id = intent.id
                 AND a.action = 'approve' AND a.approver_id <> intent.requested_by_party_id
          ) AS v;
        IF approvals < intent.approval_threshold
           OR NEW.payload IS DISTINCT FROM jsonb_build_object(
                'bridge_version', '1',
                'intent_id', intent.id::text,
                'request_id', intent.request_id::text,
                'request_hash', intent.request_hash,
                'approval_threshold', intent.approval_threshold,
                'approval_count', approvals,
                'approved_by_party_ids', voter_ids,
                'request', intent.request_payload
           )
           OR NEW.payload->>'approval_threshold' IS DISTINCT FROM intent.approval_threshold::text
           OR NEW.payload->>'approval_count' IS DISTINCT FROM approvals::text
           OR NEW.payload->'approved_by_party_ids' IS DISTINCT FROM voter_ids THEN
            RAISE EXCEPTION 'human approval quorum has not been met or outbox approvals do not match';
        END IF;
        RETURN NEW;
    END IF;
    IF OLD.intent_id IS DISTINCT FROM NEW.intent_id OR OLD.payload IS DISTINCT FROM NEW.payload
       OR OLD.payload_hash IS DISTINCT FROM NEW.payload_hash THEN
        RAISE EXCEPTION 'outbox payload is immutable';
    END IF;
    IF OLD.delivery_status = 'ready' AND NEW.delivery_status = 'dispatched' THEN
        SELECT * INTO intent FROM public.protocol_execution_intent WHERE id = NEW.intent_id FOR UPDATE;
        SELECT * INTO crosswalk FROM public.protocol_project_location WHERE id = intent.mapping_id FOR UPDATE;
        IF intent.status <> 'approved' OR crosswalk.status <> 'active'
           OR (intent.request_payload->>'expires_at')::timestamptz <= NOW() THEN
            RAISE EXCEPTION 'approved intent, active crosswalk, and unexpired request are required before dispatch';
        END IF;
        SELECT count(DISTINCT a.approver_id) INTO approvals
          FROM public.approval a JOIN public.party p ON p.id = a.approver_id AND p.party_type = 'person'
         WHERE a.collection = 'protocol_execution_intent' AND a.record_id = intent.id
           AND a.action = 'approve' AND a.approver_id <> intent.requested_by_party_id;
        IF approvals < intent.approval_threshold THEN
            RAISE EXCEPTION 'human approval quorum has not been met';
        END IF;
        RETURN NEW;
    ELSIF OLD.delivery_status = NEW.delivery_status THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'invalid outbox delivery transition: % -> %', OLD.delivery_status, NEW.delivery_status;
END;
$$;
CREATE TRIGGER trg_protocol_execution_outbox_guard
    BEFORE INSERT OR UPDATE ON public.protocol_execution_outbox
    FOR EACH ROW EXECUTE FUNCTION public.guard_protocol_execution_outbox();

CREATE OR REPLACE FUNCTION public.guard_protocol_execution_reconciliation()
RETURNS TRIGGER LANGUAGE plpgsql SET search_path = pg_catalog AS $$
DECLARE
    intent public.protocol_execution_intent%ROWTYPE;
    request_chain TEXT;
    request_effect TEXT;
    reviewer_type TEXT;
BEGIN
    IF TG_OP = 'INSERT' THEN
        SELECT * INTO intent FROM public.protocol_execution_intent WHERE id = NEW.intent_id;
        IF intent.id IS NULL OR intent.status <> 'approved'
           OR NEW.finality_status <> 'finalized'
           OR lower(NEW.expected_effect_hash) <> lower(NEW.observed_effect_hash)
           OR NOT EXISTS (
               SELECT 1 FROM public.protocol_execution_outbox o
               WHERE o.intent_id = intent.id AND o.delivery_status = 'dispatched'
           ) THEN
            RAISE EXCEPTION 'reconciliation requires dispatched, finalized, effect-matched execution evidence';
        END IF;
        request_chain := intent.request_payload->>'chain_id';
        request_effect := intent.request_payload->>'expected_effect_hash';
        IF request_chain IS DISTINCT FROM NEW.chain_id::text
           OR lower(request_effect) IS DISTINCT FROM lower(NEW.expected_effect_hash) THEN
            RAISE EXCEPTION 'reconciliation chain or effect commitment differs from approved request';
        END IF;
        RETURN NEW;
    END IF;
    IF NEW.intent_id IS DISTINCT FROM OLD.intent_id OR NEW.chain_id IS DISTINCT FROM OLD.chain_id
       OR NEW.transaction_hash IS DISTINCT FROM OLD.transaction_hash
       OR NEW.receipt_block_number IS DISTINCT FROM OLD.receipt_block_number
       OR NEW.receipt_block_hash IS DISTINCT FROM OLD.receipt_block_hash
       OR NEW.expected_effect_hash IS DISTINCT FROM OLD.expected_effect_hash
       OR NEW.observed_effect_hash IS DISTINCT FROM OLD.observed_effect_hash
       OR NEW.finality_status IS DISTINCT FROM OLD.finality_status
       OR NEW.evidence IS DISTINCT FROM OLD.evidence THEN
        RAISE EXCEPTION 'destination evidence is immutable';
    END IF;
    IF OLD.review_status = 'submitted' AND NEW.review_status IN ('verified', 'rejected')
       AND NEW.reviewed_by_party_id IS NOT NULL AND NEW.reviewed_at IS NOT NULL THEN
        SELECT party_type INTO reviewer_type FROM public.party WHERE id = NEW.reviewed_by_party_id;
        IF reviewer_type IS DISTINCT FROM 'person' THEN
            RAISE EXCEPTION 'reconciliation reviewer must be an identified human party' USING ERRCODE = '42501';
        END IF;
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'invalid reconciliation review transition: % -> %', OLD.review_status, NEW.review_status;
END;
$$;
CREATE TRIGGER trg_protocol_execution_reconciliation_guard
    BEFORE INSERT OR UPDATE ON public.protocol_execution_reconciliation
    FOR EACH ROW EXECUTE FUNCTION public.guard_protocol_execution_reconciliation();

COMMIT;
