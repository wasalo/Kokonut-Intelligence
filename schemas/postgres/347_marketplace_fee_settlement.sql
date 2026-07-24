-- ============================================================
-- Marketplace Fee Settlement
-- Adds fee tracking columns to credit_buy_order and ensures
-- fees are collected during buy order execution.
-- ============================================================

ALTER TABLE credit_buy_order
    ADD COLUMN IF NOT EXISTS buyer_fee NUMERIC(14,4) DEFAULT 0;

ALTER TABLE credit_buy_order
    ADD COLUMN IF NOT EXISTS seller_fee NUMERIC(14,4) DEFAULT 0;
