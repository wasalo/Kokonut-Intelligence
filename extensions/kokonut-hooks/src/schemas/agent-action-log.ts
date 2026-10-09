import { z } from 'zod';
import { uuidSchema, isoDateSchema } from './common.js';

const HIGH_RISK_ACTIONS = [
  'publish',
  'attest',
  'onchain_submit',
  'delete',
  'bulk_update',
  'financial_write',
  'status_change_to_published',
] as const;

export const agentActionLogCreateSchema = z
  .object({
    action: z.enum(HIGH_RISK_ACTIONS).optional(),
    collection: z.string().optional(),
    record_id: uuidSchema.optional(),
    actor_type: z.string().optional(),
    actor_id: uuidSchema.optional(),
    high_risk: z.boolean().optional(),
    requires_human_approval: z.boolean().optional(),
    notes: z.string().optional(),
    occurred_at: isoDateSchema.optional(),
  })
  .passthrough();

export const agentActionLogUpdateSchema = agentActionLogCreateSchema.partial();

export function validateAgentActionLogCreate(payload: Record<string, any>): Record<string, any> {
  return agentActionLogCreateSchema.parse(payload);
}

export function validateAgentActionLogUpdate(payload: Record<string, any>): Record<string, any> {
  return agentActionLogUpdateSchema.parse(payload);
}
