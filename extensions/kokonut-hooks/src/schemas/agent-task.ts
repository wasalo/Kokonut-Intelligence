import { z } from 'zod';
import { uuidSchema, isoDateSchema, lifecycleStatusSchema } from './common.js';

const AGENT_REVIEW_STATUSES = ['draft', 'submitted', 'rejected'] as const;

export const agentTaskCreateSchema = z
  .object({
    task_type: z.string().min(1, 'task_type is required'),
    title: z.string().min(1).optional(),
    description: z.string().optional(),
    location_id: uuidSchema.optional(),
    assignee_type: z.string().optional(),
    assignee_id: uuidSchema.optional(),
    status: lifecycleStatusSchema.optional(),
    review_status: z.enum(AGENT_REVIEW_STATUSES).optional(),
    high_risk: z.boolean().optional(),
    requires_human_approval: z.boolean().optional(),
    due_date: isoDateSchema.optional(),
  })
  .passthrough();

export const agentTaskUpdateSchema = agentTaskCreateSchema.partial();

export function validateAgentTaskCreate(payload: Record<string, any>): Record<string, any> {
  return agentTaskCreateSchema.parse(payload);
}

export function validateAgentTaskUpdate(payload: Record<string, any>): Record<string, any> {
  return agentTaskUpdateSchema.parse(payload);
}
