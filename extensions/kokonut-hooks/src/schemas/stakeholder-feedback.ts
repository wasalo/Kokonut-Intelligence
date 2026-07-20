import { z } from 'zod';
import { uuidSchema, lifecycleStatusSchema, isoDateSchema } from './common.js';

const PUBLIC_CONSENT_SCOPES = new Set([
  'public_review',
  'public_insight',
  'research',
  'marketing',
]);

export const stakeholderFeedbackCreateSchema = z
  .object({
    farmer_id: z.string().optional(),
    location_id: uuidSchema.optional(),
    feedback_type: z.string().optional(),
    content: z.string().min(1, 'content is required').optional(),
    status: lifecycleStatusSchema.optional(),
    is_public: z.boolean().optional(),
    consent_given: z.boolean().optional(),
    consent_scope: z.string().optional(),
    public_summary: z.string().optional(),
    evidence_maturity: z.number().int().min(1).max(6).optional(),
    submitted_by: uuidSchema.optional(),
    submitted_at: isoDateSchema.optional(),
  })
  .passthrough()
  .superRefine((val, ctx) => {
    if (val.is_public === true) {
      if (val.consent_given !== true) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ['consent_given'],
          message: 'Public feedback requires consent_given=true',
        });
      }
      if (!val.consent_scope || !PUBLIC_CONSENT_SCOPES.has(val.consent_scope)) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ['consent_scope'],
          message: 'Public feedback requires a valid consent_scope',
        });
      }
      if (val.status !== 'published') {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ['status'],
          message: 'Public feedback requires status=published',
        });
      }
      if (!val.public_summary || !String(val.public_summary).trim()) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ['public_summary'],
          message: 'Public feedback requires a non-empty public_summary',
        });
      }
    }
  });

// Updates may supply a subset of fields; the public-consent rule still applies
// to any supplied public fields, but unknown omitted fields must not fail.
export const stakeholderFeedbackUpdateSchema = stakeholderFeedbackCreateSchema;

export function validateStakeholderFeedbackCreate(payload: Record<string, any>): Record<string, any> {
  return stakeholderFeedbackCreateSchema.parse(payload);
}

export function validateStakeholderFeedbackUpdate(payload: Record<string, any>): Record<string, any> {
  return stakeholderFeedbackUpdateSchema.parse(payload);
}
