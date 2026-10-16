-- Add the durable delivery-state columns used by migration 409 acceptance.

ALTER TABLE public.notification_outbox
    ADD COLUMN status TEXT NOT NULL DEFAULT 'pending',
    ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0;

CREATE TABLE public.notification_outbox_attempt (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    outbox_id UUID NOT NULL REFERENCES public.notification_outbox(id),
    attempt_number INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'processing'
);
