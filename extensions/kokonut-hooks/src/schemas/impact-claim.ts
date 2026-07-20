import { z } from 'zod';
import { uuidSchema, evidenceMaturitySchema, lifecycleStatusSchema, isoDateSchema } from './common.js';

export const impactClaimCreateSchema = z
  .object({
    claim_category: z.enum(['carbon', 'biodiversity', 'social', 'financial', 'other']).optional(),
    claim_type: z.string().optional(),
    status: lifecycleStatusSchema.optional(),
    public_claim: z.boolean().optional(),
    evidence_maturity: evidenceMaturitySchema.optional(),
    external_verifier: z.string().optional(),
    methodology_ref: z.string().optional(),
    impact_value: z.number().optional(),
    impact_unit: z.string().optional(),
    location_id: uuidSchema.optional(),
    published_at: isoDateSchema.optional(),
  })
  .passthrough();

export const impactClaimUpdateSchema = impactClaimCreateSchema.partial();

export function validateImpactClaimCreate(payload: Record<string, any>): Record<string, any> {
  return impactClaimCreateSchema.parse(payload);
}

export function validateImpactClaimUpdate(payload: Record<string, any>): Record<string, any> {
  return impactClaimUpdateSchema.parse(payload);
}
