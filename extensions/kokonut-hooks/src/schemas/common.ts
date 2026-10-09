import { z } from 'zod';

/** Directus UUID v4 string. */
export const uuidSchema = z
  .string()
  .uuid({ message: 'Value must be a valid UUID' });

/** ISO-8601 date or timestamp string. */
export const isoDateSchema = z
  .string()
  .regex(
    /^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2})?(\.\d+)?(Z|[+-]\d{2}:?\d{2})?)?$/,
    'Value must be an ISO-8601 date or timestamp'
  );

/** 0x-prefixed Ethereum address. */
export const ethAddressSchema = z
  .string()
  .regex(/^0x[a-fA-F0-9]{40}$/, 'Value must be a valid Ethereum address');

/** Non-negative numeric quantity. */
export const nonNegativeNumberSchema = z
  .number({ invalid_type_error: 'Value must be a number' })
  .nonnegative('Value must not be negative');

/** Governed lifecycle status enum (per workflow.ts STANDARD_TRANSITIONS). */
export const lifecycleStatusSchema = z.enum([
  'draft',
  'submitted',
  'verified',
  'rejected',
  'published',
]);

/** Evidence maturity level 1-6 (per AGENTS.md public-claim gating). */
export const evidenceMaturitySchema = z
  .number({ invalid_type_error: 'Evidence maturity must be a number' })
  .int()
  .min(1)
  .max(6);

/** Sanitize Zod errors into concise, non-leaking messages. */
export function formatZodError(error: z.ZodError): string {
  const messages = error.issues.map((issue) => {
    const path = issue.path.join('.') || '(root)';
    return `${path}: ${issue.message}`;
  });
  return `Validation failed: ${messages.join('; ')}`;
}
