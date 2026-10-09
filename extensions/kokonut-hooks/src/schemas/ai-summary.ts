import { z } from 'zod';
import { uuidSchema, lifecycleStatusSchema, isoDateSchema } from './common.js';

const AI_STATUSES = ['draft', 'submitted', 'rejected'] as const;

export const aiSummaryCreateSchema = z
  .object({
    location_id: uuidSchema.optional(),
    org_id: uuidSchema.optional(),
    summary_type: z.string().min(1).optional(),
    title: z.string().min(1).optional(),
    content: z.string().optional(),
    status: z.enum(AI_STATUSES).optional(),
    generated_by: uuidSchema.optional(),
    model: z.string().optional(),
    confidence_score: z.number().min(0).max(1).optional(),
    published_at: isoDateSchema.optional(),
  })
  .passthrough();

export const aiSummaryUpdateSchema = aiSummaryCreateSchema.partial();

export function validateAiSummaryCreate(payload: Record<string, any>): Record<string, any> {
  return aiSummaryCreateSchema.parse(payload);
}

export function validateAiSummaryUpdate(payload: Record<string, any>): Record<string, any> {
  return aiSummaryUpdateSchema.parse(payload);
}
