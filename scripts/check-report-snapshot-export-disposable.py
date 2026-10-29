#!/usr/bin/env python3
"""Replay migrations 683-685 and exercise scoped report exports on disposable PG 16."""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "schemas/postgres/683_location_scoped_report_snapshot_exports.sql"
CANDIDATE_MIGRATION = ROOT / "schemas/postgres/684_report_snapshot_export_candidates.sql"
REQUESTER_ISOLATION_MIGRATION = ROOT / "schemas/postgres/685_report_snapshot_export_requester_isolation.sql"
DEFAULT_OUTPUT = ROOT / "docs/refactor/builds/2026-10-29-recovery/report-snapshot-export-migration-disposable.json"

ORG_A = "10000000-0000-0000-0000-000000000001"
ORG_B = "10000000-0000-0000-0000-000000000002"
LOCATION_A = "20000000-0000-0000-0000-000000000001"
LOCATION_B = "20000000-0000-0000-0000-000000000002"
OPERATOR_A = "30000000-0000-0000-0000-000000000001"
OPERATOR_B = "30000000-0000-0000-0000-000000000002"
SNAPSHOT_A = "40000000-0000-0000-0000-000000000001"
SNAPSHOT_A_DRAFT = "40000000-0000-0000-0000-000000000002"
SNAPSHOT_A_OTHER = "40000000-0000-0000-0000-000000000003"
SNAPSHOT_B = "40000000-0000-0000-0000-000000000004"
SNAPSHOT_BAD_HASH = "40000000-0000-0000-0000-000000000005"
SNAPSHOT_TOO_LARGE = "40000000-0000-0000-0000-000000000006"
EXPORT_HASH = hashlib.sha256(json.dumps({"value": 1}, sort_keys=True).encode()).hexdigest()
OTHER_HASH = hashlib.sha256(json.dumps({"value": 2}, sort_keys=True).encode()).hexdigest()

FIXTURE = f"""
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE ROLE kokonut_runtime LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE kokonut_directus_runtime NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;

CREATE SCHEMA kokonut_security;
CREATE TABLE kokonut_security.test_context_key (
    id BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (id), secret BYTEA NOT NULL
);
INSERT INTO kokonut_security.test_context_key(secret) VALUES (decode(repeat('a', 64), 'hex'));
CREATE FUNCTION kokonut_security.current_tenant_context()
RETURNS TABLE(tenant_id UUID, location_id UUID, actor_id UUID, actor_type TEXT)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE payload_text TEXT; signature_text TEXT; secret BYTEA; payload JSONB;
BEGIN
    payload_text := pg_catalog.current_setting('kokonut.context_payload', TRUE);
    signature_text := pg_catalog.current_setting('kokonut.context_signature', TRUE);
    SELECT context_key.secret INTO secret FROM kokonut_security.test_context_key AS context_key WHERE context_key.id;
    IF payload_text IS NULL OR signature_text IS NULL OR secret IS NULL
       OR signature_text IS DISTINCT FROM pg_catalog.encode(
           public.hmac(pg_catalog.convert_to(payload_text, 'UTF8'), secret, 'sha256'), 'hex'
       ) THEN
        RETURN;
    END IF;
    payload := payload_text::JSONB;
    RETURN QUERY SELECT (payload->>'tenant_id')::UUID, (payload->>'location_id')::UUID,
                        (payload->>'actor_id')::UUID, payload->>'actor_type';
END;
$$;
CREATE FUNCTION kokonut_security.test_set_context(requested_tenant UUID, requested_location UUID, requested_actor UUID)
RETURNS VOID LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE payload_text TEXT; secret BYTEA;
BEGIN
    payload_text := pg_catalog.jsonb_build_object(
        'tenant_id', requested_tenant, 'location_id', requested_location,
        'actor_id', requested_actor, 'actor_type', 'operator'
    )::TEXT;
    SELECT context_key.secret INTO secret FROM kokonut_security.test_context_key AS context_key WHERE context_key.id;
    PERFORM pg_catalog.set_config('kokonut.context_payload', payload_text, TRUE);
    PERFORM pg_catalog.set_config(
        'kokonut.context_signature',
        pg_catalog.encode(public.hmac(pg_catalog.convert_to(payload_text, 'UTF8'), secret, 'sha256'), 'hex'),
        TRUE
    );
END;
$$;
REVOKE ALL ON FUNCTION kokonut_security.test_set_context(UUID, UUID, UUID) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.test_set_context(UUID, UUID, UUID) TO kokonut_runtime;

CREATE TABLE public.organization (id UUID PRIMARY KEY, status TEXT NOT NULL);
CREATE TABLE public.location (id UUID PRIMARY KEY, organization_id UUID NOT NULL REFERENCES public.organization(id), status TEXT NOT NULL);
CREATE TABLE public.location_tenant_owner_verification (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), location_id UUID NOT NULL REFERENCES public.location(id),
    organization_id UUID NOT NULL REFERENCES public.organization(id), revoked_at TIMESTAMPTZ
);
CREATE TABLE public.operator_identity (id UUID PRIMARY KEY, enabled BOOLEAN NOT NULL);
CREATE TABLE public.operator_organization_membership (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), operator_id UUID NOT NULL REFERENCES public.operator_identity(id),
    organization_id UUID NOT NULL REFERENCES public.organization(id), revoked_at TIMESTAMPTZ
);
CREATE TABLE public.location_organization_share (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), location_id UUID NOT NULL REFERENCES public.location(id),
    organization_id UUID NOT NULL REFERENCES public.organization(id), revoked_at TIMESTAMPTZ, expires_at TIMESTAMPTZ
);
CREATE TABLE public.operator_scope_grant (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), operator_id UUID NOT NULL REFERENCES public.operator_identity(id),
    organization_id UUID, resource TEXT NOT NULL, action TEXT NOT NULL,
    location_id UUID NOT NULL REFERENCES public.location(id), revoked_at TIMESTAMPTZ
);
CREATE FUNCTION public.operator_scope_grant_allows(requested_operator UUID, requested_resource TEXT,
                                                     requested_action TEXT, requested_location UUID)
RETURNS BOOLEAN LANGUAGE SQL STABLE SECURITY INVOKER AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.operator_scope_grant AS grant_row
        JOIN public.operator_identity AS identity ON identity.id = grant_row.operator_id AND identity.enabled
        JOIN public.location AS loc ON loc.id = grant_row.location_id
        WHERE grant_row.operator_id = requested_operator
          AND grant_row.resource = requested_resource AND grant_row.action = requested_action
          AND grant_row.location_id = requested_location AND grant_row.revoked_at IS NULL
          AND (
            grant_row.organization_id IS NULL OR (
              EXISTS (SELECT 1 FROM public.operator_organization_membership AS membership
                       JOIN public.organization AS tenant ON tenant.id = membership.organization_id
                           AND tenant.status = 'active'
                      WHERE membership.operator_id = grant_row.operator_id
                        AND membership.organization_id = grant_row.organization_id
                        AND membership.revoked_at IS NULL)
              AND EXISTS (SELECT 1 FROM public.location_tenant_owner_verification AS owner
                           WHERE owner.location_id = loc.id AND owner.organization_id = loc.organization_id
                             AND owner.revoked_at IS NULL AND (
                               owner.organization_id = grant_row.organization_id OR EXISTS (
                                 SELECT 1 FROM public.location_organization_share AS share
                                  WHERE share.location_id = loc.id
                                    AND share.organization_id = grant_row.organization_id
                                    AND share.revoked_at IS NULL
                                    AND (share.expires_at IS NULL OR share.expires_at > now())
                               )
                             ))
            )
          )
    );
$$;
CREATE TABLE public.report_snapshot (
    id UUID PRIMARY KEY, report_name VARCHAR(255) NOT NULL, report_type VARCHAR(100),
    location_id UUID REFERENCES public.location(id), period_start DATE, period_end DATE,
    report_data JSONB NOT NULL, snapshot_hash VARCHAR(255), status VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp()
);

INSERT INTO public.organization VALUES ('{ORG_A}', 'active'), ('{ORG_B}', 'active');
INSERT INTO public.location VALUES ('{LOCATION_A}', '{ORG_A}', 'active'), ('{LOCATION_B}', '{ORG_B}', 'active');
INSERT INTO public.location_tenant_owner_verification(location_id, organization_id)
VALUES ('{LOCATION_A}', '{ORG_A}'), ('{LOCATION_B}', '{ORG_B}');
INSERT INTO public.operator_identity VALUES ('{OPERATOR_A}', TRUE), ('{OPERATOR_B}', TRUE);
INSERT INTO public.operator_organization_membership(operator_id, organization_id)
VALUES ('{OPERATOR_A}', '{ORG_A}'), ('{OPERATOR_B}', '{ORG_B}');
INSERT INTO public.operator_scope_grant(operator_id, organization_id, resource, action, location_id)
SELECT '{OPERATOR_A}'::UUID, '{ORG_A}'::UUID, 'report_snapshot_export', action, '{LOCATION_A}'::UUID
  FROM unnest(ARRAY['create', 'read', 'download']) AS action
UNION ALL
SELECT '{OPERATOR_B}'::UUID, '{ORG_B}'::UUID, 'report_snapshot_export', action, '{LOCATION_B}'::UUID
  FROM unnest(ARRAY['create', 'read', 'download']) AS action
UNION ALL
SELECT '{OPERATOR_B}'::UUID, '{ORG_B}'::UUID, 'report_snapshot_export', action, '{LOCATION_A}'::UUID
  FROM unnest(ARRAY['create', 'read', 'download']) AS action;
INSERT INTO public.location_organization_share(location_id, organization_id)
VALUES ('{LOCATION_A}', '{ORG_B}');
INSERT INTO public.report_snapshot (
    id, report_name, report_type, location_id, period_start, period_end,
    report_data, snapshot_hash, status
) VALUES
  ('{SNAPSHOT_A}', 'Synthetic report A', 'impact', '{LOCATION_A}', NULL, NULL, '{{"value":1}}'::jsonb, '{EXPORT_HASH}', 'verified'),
  ('{SNAPSHOT_A_DRAFT}', 'Synthetic draft', 'impact', '{LOCATION_A}', NULL, NULL, '{{"value":1}}'::jsonb, '{EXPORT_HASH}', 'draft'),
  ('{SNAPSHOT_A_OTHER}', 'Synthetic report A2', 'impact', '{LOCATION_A}', NULL, NULL, '{{"value":2}}'::jsonb, '{OTHER_HASH}', 'published'),
  ('{SNAPSHOT_B}', 'Synthetic report B', 'impact', '{LOCATION_B}', NULL, NULL, '{{"value":1}}'::jsonb, '{EXPORT_HASH}', 'verified');
INSERT INTO public.report_snapshot (
    id, report_name, report_type, location_id, report_data, snapshot_hash, status
) VALUES
  ('{SNAPSHOT_BAD_HASH}', 'Synthetic malformed digest', 'impact', '{LOCATION_A}', '{{"value":3}}'::jsonb, 'not-a-sha256', 'verified'),
  ('{SNAPSHOT_TOO_LARGE}', 'Synthetic oversized report', 'impact', '{LOCATION_A}',
   pg_catalog.jsonb_build_object('payload', pg_catalog.repeat('x', 524289)), '{OTHER_HASH}', 'verified');

ALTER TABLE public.organization ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.organization FORCE ROW LEVEL SECURITY;
ALTER TABLE public.location ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.location FORCE ROW LEVEL SECURITY;
ALTER TABLE public.location_tenant_owner_verification ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.location_tenant_owner_verification FORCE ROW LEVEL SECURITY;
ALTER TABLE public.operator_identity ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.operator_identity FORCE ROW LEVEL SECURITY;
ALTER TABLE public.operator_organization_membership ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.operator_organization_membership FORCE ROW LEVEL SECURITY;
ALTER TABLE public.location_organization_share ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.location_organization_share FORCE ROW LEVEL SECURITY;
ALTER TABLE public.operator_scope_grant ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.operator_scope_grant FORCE ROW LEVEL SECURITY;
ALTER TABLE public.report_snapshot ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.report_snapshot FORCE ROW LEVEL SECURITY;
"""

REPLAY_SETUP = """
ALTER ROLE kokonut_report_snapshot_export_login WITH LOGIN PASSWORD 'synthetic-report-export-worker-password';
GRANT ALL PRIVILEGES ON TABLE public.report_snapshot_export_request,
    public.report_snapshot_export_attempt TO kokonut_runtime, kokonut_directus_runtime,
    kokonut_report_snapshot_export_login;
"""

ACCEPTANCE = f"""
SET SESSION AUTHORIZATION kokonut_runtime;
DO $$
DECLARE request_row RECORD; request_id UUID; count_rows INTEGER;
BEGIN
    IF NOT has_function_privilege('kokonut_runtime', 'kokonut_security.request_report_snapshot_export(uuid,uuid,uuid)', 'EXECUTE')
       OR NOT has_function_privilege('kokonut_runtime', 'kokonut_security.list_report_snapshot_exports(uuid,integer)', 'EXECUTE')
       OR NOT has_function_privilege('kokonut_runtime', 'kokonut_security.get_report_snapshot_export(uuid,uuid)', 'EXECUTE')
       OR NOT has_function_privilege('kokonut_runtime', 'kokonut_security.authorize_report_snapshot_export_download(uuid,uuid)', 'EXECUTE') THEN
        RAISE EXCEPTION 'runtime is missing one or more user export functions';
    END IF;
    IF has_function_privilege('kokonut_directus_runtime', 'kokonut_security.request_report_snapshot_export(uuid,uuid,uuid)', 'EXECUTE')
       OR has_function_privilege('kokonut_runtime', 'kokonut_security.claim_report_snapshot_export_batch(text,integer,integer)', 'EXECUTE')
       OR has_function_privilege('kokonut_runtime', 'kokonut_security.read_report_snapshot_export_source(uuid,text,uuid)', 'EXECUTE')
       OR has_function_privilege('kokonut_runtime', 'kokonut_security.finish_report_snapshot_export_attempt(uuid,text,uuid,boolean,text,integer,uuid,text,bigint)', 'EXECUTE') THEN
        RAISE EXCEPTION 'runtime or Directus crossed the user/worker function boundary';
    END IF;
    IF has_table_privilege('kokonut_runtime', 'public.report_snapshot_export_request', 'SELECT')
       OR has_table_privilege('kokonut_runtime', 'public.report_snapshot_export_request', 'INSERT')
       OR has_table_privilege('kokonut_directus_runtime', 'public.report_snapshot_export_attempt', 'SELECT')
       OR has_table_privilege('kokonut_report_snapshot_export_login', 'public.report_snapshot_export_request', 'SELECT') THEN
        RAISE EXCEPTION 'runtime, Directus, or worker retains direct export table access after migration replay';
    END IF;
    IF (SELECT count(*) FROM pg_catalog.pg_policies WHERE schemaname = 'public'
        AND policyname LIKE 'report_export_%_select') <> 8 THEN
        RAISE EXCEPTION 'source relations with FORCE RLS do not have all owner SELECT policies';
    END IF;
    PERFORM set_config('kokonut.test.export.request_a', '', FALSE);
    PERFORM kokonut_security.test_set_context('{ORG_A}', '{LOCATION_A}', '{OPERATOR_A}');
    SELECT * INTO request_row FROM kokonut_security.request_report_snapshot_export(
        '{LOCATION_A}', '{SNAPSHOT_A}', '50000000-0000-0000-0000-000000000001'
    );
    IF request_row.request_id IS NULL OR request_row.status <> 'pending' THEN
        RAISE EXCEPTION 'valid signed create request did not create a pending export';
    END IF;
    request_id := request_row.request_id;
    PERFORM set_config('kokonut.test.export.request_a', request_id::TEXT, FALSE);
    SELECT * INTO request_row FROM kokonut_security.request_report_snapshot_export(
        '{LOCATION_A}', '{SNAPSHOT_A}', '50000000-0000-0000-0000-000000000001'
    );
    IF request_row.request_id IS DISTINCT FROM request_id THEN
        RAISE EXCEPTION 'same idempotency request did not return the original request';
    END IF;
    BEGIN
        PERFORM * FROM kokonut_security.request_report_snapshot_export(
            '{LOCATION_A}', '{SNAPSHOT_A_OTHER}', '50000000-0000-0000-0000-000000000001'
        );
        RAISE EXCEPTION 'same idempotency key with different source unexpectedly succeeded';
    EXCEPTION WHEN unique_violation THEN NULL;
    END;
    PERFORM set_config('kokonut.test.export.request_draft', 'not-created', FALSE);
    IF EXISTS (SELECT 1 FROM kokonut_security.request_report_snapshot_export(
        '{LOCATION_A}', '{SNAPSHOT_A_DRAFT}', '50000000-0000-0000-0000-000000000002'
    )) THEN
        RAISE EXCEPTION 'draft snapshot was unexpectedly exportable';
    END IF;
    SELECT * INTO request_row FROM kokonut_security.request_report_snapshot_export(
        '{LOCATION_A}', '{SNAPSHOT_A_OTHER}', '50000000-0000-0000-0000-000000000005'
    );
    IF request_row.request_id IS NULL THEN
        RAISE EXCEPTION 'second eligible snapshot request did not create';
    END IF;
    PERFORM set_config('kokonut.test.export.request_b', request_row.request_id::TEXT, FALSE);
    BEGIN
        PERFORM * FROM kokonut_security.request_report_snapshot_export(
            '{LOCATION_B}', '{SNAPSHOT_B}', '50000000-0000-0000-0000-000000000003'
        );
        RAISE EXCEPTION 'mismatched signed location unexpectedly succeeded';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    PERFORM kokonut_security.test_set_context('{ORG_B}', '{LOCATION_B}', '{OPERATOR_B}');
    BEGIN
        PERFORM * FROM kokonut_security.request_report_snapshot_export(
            '{LOCATION_A}', '{SNAPSHOT_A}', '50000000-0000-0000-0000-000000000004'
        );
        RAISE EXCEPTION 'cross-operator location request unexpectedly succeeded';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    PERFORM kokonut_security.test_set_context('{ORG_A}', '{LOCATION_A}', '{OPERATOR_A}');
    SELECT count(*) INTO count_rows
      FROM kokonut_security.list_report_snapshot_exports('{LOCATION_A}', 50);
    IF count_rows <> 2 THEN RAISE EXCEPTION 'location-scoped export list did not return exactly two rows'; END IF;
    BEGIN
        PERFORM * FROM kokonut_security.get_report_snapshot_export('{LOCATION_B}', request_id);
        RAISE EXCEPTION 'cross-location export detail unexpectedly succeeded';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    PERFORM kokonut_security.test_set_context('{ORG_B}', '{LOCATION_A}', '{OPERATOR_B}');
    IF EXISTS (SELECT 1 FROM kokonut_security.list_report_snapshot_exports('{LOCATION_A}', 50)) THEN
        RAISE EXCEPTION 'same-location operator saw another operator export status';
    END IF;
    IF EXISTS (SELECT 1 FROM kokonut_security.get_report_snapshot_export('{LOCATION_A}', request_id)) THEN
        RAISE EXCEPTION 'same-location operator saw another operator export detail';
    END IF;
    SELECT count(*) INTO count_rows
      FROM kokonut_security.list_report_snapshot_export_candidates('{LOCATION_A}', 25, 0);
    IF count_rows <> 2 THEN
        RAISE EXCEPTION 'shared location read grant did not preserve candidate visibility';
    END IF;
    PERFORM kokonut_security.test_set_context('{ORG_A}', '{LOCATION_A}', '{OPERATOR_A}');
    IF EXISTS (SELECT 1 FROM kokonut_security.authorize_report_snapshot_export_download(
        '{LOCATION_A}', request_id
    )) THEN RAISE EXCEPTION 'pending export unexpectedly authorized download'; END IF;
END;
$$;
RESET SESSION AUTHORIZATION;

SET SESSION AUTHORIZATION kokonut_report_snapshot_export_login;
DO $$
DECLARE claimed RECORD; result TEXT; invalid_claim BOOLEAN := FALSE;
BEGIN
    IF session_user <> 'kokonut_report_snapshot_export_login' THEN
        RAISE EXCEPTION 'dedicated worker identity was not established';
    END IF;
    BEGIN
        PERFORM * FROM kokonut_security.claim_report_snapshot_export_batch('worker-a', 26, 60);
        RAISE EXCEPTION 'claim over 25 unexpectedly succeeded';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        PERFORM 1 FROM public.report_snapshot_export_request;
        RAISE EXCEPTION 'worker direct table read unexpectedly succeeded';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        PERFORM 1 FROM public.report_snapshot_export_attempt;
        RAISE EXCEPTION 'worker direct receipt read unexpectedly succeeded';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    SELECT * INTO claimed FROM kokonut_security.claim_report_snapshot_export_batch('worker-a', 1, 120);
    IF NOT FOUND OR claimed.snapshot_id <> '{SNAPSHOT_A}' OR claimed.attempt_count <> 1
       OR claimed.lease_token IS NULL THEN
        RAISE EXCEPTION 'bounded worker claim failed';
    END IF;
    IF EXISTS (SELECT 1 FROM kokonut_security.read_report_snapshot_export_source(
        claimed.request_id, 'wrong-worker', claimed.lease_token
    )) OR EXISTS (SELECT 1 FROM kokonut_security.read_report_snapshot_export_source(
        claimed.request_id, 'worker-a', gen_random_uuid()
    )) THEN
        RAISE EXCEPTION 'source read accepted mismatched worker or token';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM kokonut_security.read_report_snapshot_export_source(
        claimed.request_id, 'worker-a', claimed.lease_token
    ) AS source WHERE source.id = '{SNAPSHOT_A}' AND source.location_id = '{LOCATION_A}'
        AND source.status = 'verified' AND source.report_data = '{{"value":1}}'::jsonb) THEN
        RAISE EXCEPTION 'valid worker lease did not return only the exact eligible source';
    END IF;
    SELECT kokonut_security.finish_report_snapshot_export_attempt(
        claimed.request_id, 'wrong-worker', claimed.lease_token, TRUE, NULL, 0,
        '60000000-0000-0000-0000-000000000001', repeat('b',64), 120
    ) INTO result;
    IF result <> 'lease_lost' THEN RAISE EXCEPTION 'wrong worker completed a lease'; END IF;
    SELECT kokonut_security.finish_report_snapshot_export_attempt(
        claimed.request_id, 'worker-a', claimed.lease_token, TRUE, NULL, 0,
        '60000000-0000-0000-0000-000000000001', repeat('b',64), 120
    ) INTO result;
    IF result <> 'completed' THEN RAISE EXCEPTION 'valid artifact completion failed'; END IF;
    SELECT kokonut_security.finish_report_snapshot_export_attempt(
        claimed.request_id, 'worker-a', claimed.lease_token, TRUE, NULL, 0,
        '60000000-0000-0000-0000-000000000001', repeat('b',64), 120
    ) INTO result;
    IF result <> 'lease_lost' THEN RAISE EXCEPTION 'duplicate completion was not fenced'; END IF;
    SELECT * INTO claimed FROM kokonut_security.claim_report_snapshot_export_batch('worker-a', 1, 120);
    IF NOT FOUND OR claimed.snapshot_id <> '{SNAPSHOT_A_OTHER}' OR claimed.attempt_count <> 1 THEN
        RAISE EXCEPTION 'second request was not claimed after the first completed';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM kokonut_security.read_report_snapshot_export_source(
        claimed.request_id, 'worker-a', claimed.lease_token
    ) AS source WHERE source.id = '{SNAPSHOT_A_OTHER}' AND source.location_id = '{LOCATION_A}') THEN
        RAISE EXCEPTION 'eligible second source was not available under a valid lease';
    END IF;
    PERFORM set_config('kokonut.test.export.request_b', claimed.request_id::TEXT, FALSE);
    PERFORM set_config('kokonut.test.export.token_b', claimed.lease_token::TEXT, FALSE);
END;
$$;
RESET SESSION AUTHORIZATION;

UPDATE public.report_snapshot SET status = 'draft' WHERE id = '{SNAPSHOT_A_OTHER}';
SET SESSION AUTHORIZATION kokonut_report_snapshot_export_login;
DO $$
DECLARE result TEXT;
BEGIN
    SELECT kokonut_security.finish_report_snapshot_export_attempt(
        current_setting('kokonut.test.export.request_b')::UUID,
        'worker-a', current_setting('kokonut.test.export.token_b')::UUID,
        TRUE, NULL, 0, '60000000-0000-0000-0000-000000000002', repeat('c',64), 100
    ) INTO result;
    IF result <> 'dead_letter' THEN
        RAISE EXCEPTION 'lifecycle-changed source did not fail closed as deterministic dead letter';
    END IF;
END;
$$;
RESET SESSION AUTHORIZATION;

SET SESSION AUTHORIZATION kokonut_runtime;
DO $$
DECLARE request_text TEXT; result RECORD;
BEGIN
    request_text := current_setting('kokonut.test.export.request_a');
    PERFORM kokonut_security.test_set_context('{ORG_A}', '{LOCATION_A}', '{OPERATOR_A}');
    SELECT * INTO result FROM kokonut_security.authorize_report_snapshot_export_download(
        '{LOCATION_A}', request_text::UUID
    );
    IF result.artifact_id IS DISTINCT FROM '60000000-0000-0000-0000-000000000001'::UUID
       OR result.artifact_sha256 IS DISTINCT FROM repeat('b',64)
       OR result.artifact_size <> 120 THEN
        RAISE EXCEPTION 'authorized completed artifact was not returned by opaque ID and digest';
    END IF;
    PERFORM kokonut_security.test_set_context('{ORG_B}', '{LOCATION_A}', '{OPERATOR_B}');
    IF EXISTS (SELECT 1 FROM kokonut_security.list_report_snapshot_exports('{LOCATION_A}', 50)) THEN
        RAISE EXCEPTION 'same-location operator saw a completed export status';
    END IF;
    IF EXISTS (SELECT 1 FROM kokonut_security.get_report_snapshot_export('{LOCATION_A}', request_text::UUID)) THEN
        RAISE EXCEPTION 'same-location operator saw completed export detail';
    END IF;
    IF EXISTS (SELECT 1 FROM kokonut_security.authorize_report_snapshot_export_download(
        '{LOCATION_A}', request_text::UUID
    )) THEN RAISE EXCEPTION 'same-location operator downloaded another operator artifact'; END IF;
    SELECT * INTO result FROM kokonut_security.request_report_snapshot_export(
        '{LOCATION_A}', '{SNAPSHOT_A}', '50000000-0000-0000-0000-000000000006'
    );
    PERFORM set_config('kokonut.test.export.request_retry', result.request_id::TEXT, FALSE);
    PERFORM kokonut_security.test_set_context('{ORG_B}', '{LOCATION_B}', '{OPERATOR_B}');
    IF EXISTS (SELECT 1 FROM kokonut_security.authorize_report_snapshot_export_download(
        '{LOCATION_B}', request_text::UUID
    )) THEN RAISE EXCEPTION 'cross-location download unexpectedly returned artifact metadata'; END IF;
END;
$$;
RESET SESSION AUTHORIZATION;

SET SESSION AUTHORIZATION kokonut_report_snapshot_export_login;
DO $$
DECLARE claimed RECORD; result TEXT;
BEGIN
    SELECT * INTO claimed FROM kokonut_security.claim_report_snapshot_export_batch('retry-worker', 1, 120);
    IF NOT FOUND OR claimed.request_id IS DISTINCT FROM current_setting('kokonut.test.export.request_retry')::UUID
       OR claimed.attempt_count <> 1 THEN
        RAISE EXCEPTION 'transient retry fixture was not claimed';
    END IF;
    SELECT kokonut_security.finish_report_snapshot_export_attempt(
        claimed.request_id, 'retry-worker', claimed.lease_token, FALSE,
        'storage_unavailable', 600, NULL, NULL, NULL
    ) INTO result;
    IF result <> 'retryable' THEN RAISE EXCEPTION 'transient failure did not remain retryable'; END IF;
    IF EXISTS (SELECT 1 FROM kokonut_security.claim_report_snapshot_export_batch('retry-worker', 1, 120)) THEN
        RAISE EXCEPTION 'retry delay was ignored by the next claim';
    END IF;
END;
$$;
RESET SESSION AUTHORIZATION;
UPDATE public.report_snapshot_export_request
   SET available_at = clock_timestamp() - interval '1 second'
 WHERE request_id = current_setting('kokonut.test.export.request_retry')::UUID;
SET SESSION AUTHORIZATION kokonut_report_snapshot_export_login;
DO $$
DECLARE claimed RECORD; result TEXT; expected_attempt INTEGER;
BEGIN
    FOR expected_attempt IN 2..8 LOOP
        SELECT * INTO claimed FROM kokonut_security.claim_report_snapshot_export_batch('retry-worker', 1, 120);
        IF NOT FOUND OR claimed.request_id IS DISTINCT FROM current_setting('kokonut.test.export.request_retry')::UUID
           OR claimed.attempt_count <> expected_attempt THEN
            RAISE EXCEPTION 'retry claim attempt % was not bounded or sequenced', expected_attempt;
        END IF;
        SELECT kokonut_security.finish_report_snapshot_export_attempt(
            claimed.request_id, 'retry-worker', claimed.lease_token, FALSE,
            'storage_unavailable', 0, NULL, NULL, NULL
        ) INTO result;
        IF (expected_attempt < 8 AND result <> 'retryable')
           OR (expected_attempt = 8 AND result <> 'dead_letter') THEN
            RAISE EXCEPTION 'retry/dead-letter transition is incorrect at attempt %', expected_attempt;
        END IF;
    END LOOP;
END;
$$;
RESET SESSION AUTHORIZATION;

DO $$
BEGIN
    IF (SELECT status FROM public.report_snapshot_export_request
         WHERE request_id = current_setting('kokonut.test.export.request_a')::UUID) <> 'completed'
       OR (SELECT count(*) FROM public.report_snapshot_export_attempt
            WHERE request_id = current_setting('kokonut.test.export.request_a')::UUID
              AND event_kind = 'claimed') <> 1
       OR (SELECT count(*) FROM public.report_snapshot_export_attempt
            WHERE request_id = current_setting('kokonut.test.export.request_a')::UUID
              AND event_kind = 'completed') <> 1 THEN
        RAISE EXCEPTION 'request transition or append-only attempt receipts were not atomic';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_proc AS procedure
        JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid=procedure.pronamespace
        WHERE namespace.nspname='kokonut_security' AND procedure.prosecdef
          AND has_function_privilege('kokonut_report_snapshot_export_login', procedure.oid, 'EXECUTE')
          AND procedure.oid IN (
              'kokonut_security.request_report_snapshot_export(uuid,uuid,uuid)'::regprocedure,
              'kokonut_security.list_report_snapshot_exports(uuid,integer)'::regprocedure,
              'kokonut_security.get_report_snapshot_export(uuid,uuid)'::regprocedure,
              'kokonut_security.authorize_report_snapshot_export_download(uuid,uuid)'::regprocedure
          )
    ) THEN RAISE EXCEPTION 'worker login can execute a user-facing export function'; END IF;
END;
$$;
"""

CANDIDATE_ACCEPTANCE = f"""
SET SESSION AUTHORIZATION kokonut_runtime;
DO $$
DECLARE result_count INTEGER; page_count INTEGER; first_snapshot UUID; returned_snapshots UUID[];
BEGIN
    IF NOT has_function_privilege(
        'kokonut_runtime',
        'kokonut_security.list_report_snapshot_export_candidates(uuid,integer,integer)',
        'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'runtime lacks bounded eligible snapshot listing function';
    END IF;
    IF has_function_privilege(
        'kokonut_directus_runtime',
        'kokonut_security.list_report_snapshot_export_candidates(uuid,integer,integer)',
        'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'Directus unexpectedly has report export candidate function access';
    END IF;
    IF pg_catalog.pg_get_function_result(
        'kokonut_security.list_report_snapshot_export_candidates(uuid,integer,integer)'::regprocedure
    ) ~ '(report_data|file_url)' THEN
        RAISE EXCEPTION 'candidate listing signature exposes private payload or storage metadata';
    END IF;
    PERFORM kokonut_security.test_set_context('{ORG_A}', '{LOCATION_A}', '{OPERATOR_A}');
    SELECT count(*) INTO result_count
      FROM kokonut_security.list_report_snapshot_export_candidates('{LOCATION_A}', 25, 0);
    SELECT array_agg(snapshot_id) INTO returned_snapshots
      FROM kokonut_security.list_report_snapshot_export_candidates('{LOCATION_A}', 25, 0);
    IF result_count <> 2 THEN
        RAISE EXCEPTION 'candidate list returned % rows (%) instead of two eligible snapshots',
            result_count, returned_snapshots;
    END IF;
    IF EXISTS (
        SELECT 1 FROM kokonut_security.list_report_snapshot_export_candidates('{LOCATION_A}', 25, 0)
         WHERE location_id <> '{LOCATION_A}'::UUID
            OR status NOT IN ('verified', 'published')
            OR snapshot_hash !~ '^[0-9a-f]{{64}}$'
    ) THEN
        RAISE EXCEPTION 'candidate list included an invalid location, state, or hash';
    END IF;
    IF EXISTS (
        SELECT 1 FROM kokonut_security.list_report_snapshot_export_candidates('{LOCATION_A}', 25, 0)
         WHERE snapshot_id NOT IN ('{SNAPSHOT_A}'::UUID, '{SNAPSHOT_A_OTHER}'::UUID)
    ) THEN
        RAISE EXCEPTION 'draft, malformed-hash, oversized, or cross-location snapshot was exposed';
    END IF;
    SELECT count(*) INTO page_count
      FROM kokonut_security.list_report_snapshot_export_candidates('{LOCATION_A}', 1, 0);
    IF page_count <> 2 THEN
        RAISE EXCEPTION 'bounded first page did not provide one-row lookahead';
    END IF;
    SELECT snapshot_id INTO first_snapshot
      FROM kokonut_security.list_report_snapshot_export_candidates('{LOCATION_A}', 1, 0)
     LIMIT 1;
    IF first_snapshot IS NULL THEN
        RAISE EXCEPTION 'candidate page ordering returned no first row';
    END IF;
    SELECT count(*) INTO page_count
      FROM kokonut_security.list_report_snapshot_export_candidates('{LOCATION_A}', 1, 1);
    IF page_count <> 1 THEN
        RAISE EXCEPTION 'second candidate page did not return one remaining row';
    END IF;
    PERFORM kokonut_security.test_set_context('{ORG_B}', '{LOCATION_B}', '{OPERATOR_B}');
    BEGIN
        PERFORM * FROM kokonut_security.list_report_snapshot_export_candidates('{LOCATION_A}', 25, 0);
        RAISE EXCEPTION 'cross-location candidate listing unexpectedly succeeded';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
END;
$$;
RESET SESSION AUTHORIZATION;

UPDATE public.operator_scope_grant SET revoked_at = pg_catalog.clock_timestamp()
 WHERE operator_id = '{OPERATOR_A}' AND resource = 'report_snapshot_export'
   AND action = 'read' AND location_id = '{LOCATION_A}' AND revoked_at IS NULL;
SET SESSION AUTHORIZATION kokonut_runtime;
DO $$
BEGIN
    PERFORM kokonut_security.test_set_context('{ORG_A}', '{LOCATION_A}', '{OPERATOR_A}');
    BEGIN
        PERFORM * FROM kokonut_security.list_report_snapshot_export_candidates('{LOCATION_A}', 25, 0);
        RAISE EXCEPTION 'candidate listing unexpectedly used a create-only grant';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
END;
$$;
RESET SESSION AUTHORIZATION;

UPDATE public.operator_scope_grant SET revoked_at = NULL
 WHERE operator_id = '{OPERATOR_A}' AND resource = 'report_snapshot_export'
   AND action = 'read' AND location_id = '{LOCATION_A}';
"""


def run(command: list[str], *, input_text: str | None = None) -> str:
    result = subprocess.run(command, input=input_text, text=True, capture_output=True, check=False)
    if result.returncode:
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(f"disposable command failed ({result.returncode}): {details}")
    return result.stdout


def docker_sql(docker: str, container: str, statement: str) -> str:
    return run(
        [docker, "exec", "-i", container, "psql", "-X", "-q", "-v", "ON_ERROR_STOP=1",
         "-U", "postgres", "-d", "postgres"],
        input_text=statement,
    )


def wait_ready(docker: str, container: str) -> None:
    deadline = time.monotonic() + 120
    # The official PostgreSQL entrypoint briefly starts a temporary server
    # during initdb. A one-shot SELECT can succeed against that server just
    # before the entrypoint stops it; keep one connection alive across the
    # handoff before applying migrations.
    stable_probe = "SELECT pg_sleep(2); SELECT 1"
    while time.monotonic() < deadline:
        result = subprocess.run(
            [docker, "exec", container, "psql", "-X", "-q", "-t", "-A",
             "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "postgres", "-c", stable_probe],
            text=True, capture_output=True, check=False,
        )
        if result.returncode == 0 and result.stdout.strip().splitlines()[-1:] == ["1"]:
            return
        time.sleep(0.25)
    raise RuntimeError("disposable PostgreSQL did not become ready and remain stable")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", type=Path)
    parser.add_argument("--image", default="postgres:16")
    parser.add_argument("--platform", choices=("linux/amd64", "linux/arm64"))
    args = parser.parse_args()
    docker = shutil.which("docker")
    if docker is None:
        raise RuntimeError("Docker CLI is unavailable")
    container = f"kokonut-report-export-{secrets.token_hex(4)}"
    output = args.output or DEFAULT_OUTPUT
    migration = MIGRATION.read_text(encoding="utf-8")
    candidate_migration = CANDIDATE_MIGRATION.read_text(encoding="utf-8")
    requester_isolation_migration = REQUESTER_ISOLATION_MIGRATION.read_text(encoding="utf-8")
    created = False
    try:
        command = [docker, "run", "-d", "--rm", "--network", "none", "--name", container]
        if args.platform is not None:
            command.extend(("--platform", args.platform))
        command.extend(("-e", f"POSTGRES_PASSWORD={secrets.token_urlsafe(24)}", args.image))
        run(command)
        created = True
        wait_ready(docker, container)
        architecture = run([docker, "exec", container, "uname", "-m"]).strip()
        expected = {"linux/amd64": "x86_64", "linux/arm64": "aarch64"}.get(args.platform)
        if expected is not None and architecture != expected:
            raise RuntimeError("disposable PostgreSQL container architecture mismatch")
        docker_sql(docker, container, FIXTURE)
        docker_sql(docker, container, migration)
        docker_sql(docker, container, candidate_migration)
        docker_sql(docker, container, requester_isolation_migration)
        docker_sql(docker, container, REPLAY_SETUP)
        docker_sql(docker, container, migration)
        docker_sql(docker, container, candidate_migration)
        docker_sql(docker, container, requester_isolation_migration)
        docker_sql(docker, container, CANDIDATE_ACCEPTANCE)
        docker_sql(docker, container, ACCEPTANCE)
        evidence = {
            "date": "2026-10-29",
            "migrations": [MIGRATION.name, CANDIDATE_MIGRATION.name, REQUESTER_ISOLATION_MIGRATION.name],
            "migration_sha256": {
                MIGRATION.name: hashlib.sha256(migration.encode()).hexdigest(),
                CANDIDATE_MIGRATION.name: hashlib.sha256(candidate_migration.encode()).hexdigest(),
                REQUESTER_ISOLATION_MIGRATION.name: hashlib.sha256(
                    requester_isolation_migration.encode()
                ).hexdigest(),
            },
            "database": "PostgreSQL 16 disposable container; Docker network disabled",
            "database_image": args.image,
            "requested_platform": args.platform,
            "container_architecture": architecture,
            "checks": [
                "migration 683 applies and replays after enabling the dedicated login",
                "signed operator tenant context, active create/read/download grants, and exact location are required",
                "only verified/published snapshots with a valid hash can be requested; idempotency collision is rejected",
                "runtime and Directus receive no export table rights; runtime has user functions only",
                "worker login has bounded claim/read/finish functions and no direct request or receipt table access",
                "forced-RLS source relations receive function-owner SELECT policies",
                "claims are bounded and lease-token/worker fenced; source loads are exact-location and lifecycle scoped",
                "download authorization returns opaque artifact UUID, digest, and size only to the current location download grant",
                "eligible snapshot listing returns only exact-location verified/published records with bounded JSON payloads and valid SHA-256 text",
                "eligible snapshot listing enforces its own read grant, preserves bounded pagination, and exposes no report payload or storage path",
                "same-location operators can list shared candidates but cannot see each other's request status/detail or download each other's artifacts",
                "request state and append-only attempt receipts commit atomically",
                "transient storage failure respects available_at and dead-letters at attempt eight; deterministic source change dead-letters immediately",
            ],
            "candidate_or_legacy_database_touched": False,
            "production_or_provider_state_established": False,
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(evidence, indent=2))
        return 0
    finally:
        if created:
            subprocess.run([docker, "rm", "-f", container], text=True, capture_output=True, check=False)


if __name__ == "__main__":
    raise SystemExit(main())
