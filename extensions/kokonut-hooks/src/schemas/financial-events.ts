import { z } from 'zod';
import { uuidSchema, nonNegativeNumberSchema, isoDateSchema } from './common.js';

export const expenseEventCreateSchema = z
  .object({
    location_id: uuidSchema.optional(),
    category: z.string().optional(),
    amount: nonNegativeNumberSchema.optional(),
    currency: z.string().min(3).max(3).optional(),
    expense_date: isoDateSchema.optional(),
    evidence_urls: z.array(z.string().url()).optional(),
    is_capital: z.boolean().optional(),
    notes: z.string().optional(),
  })
  .passthrough();

export const expenseEventUpdateSchema = expenseEventCreateSchema.partial();

export const salesEventCreateSchema = z
  .object({
    location_id: uuidSchema.optional(),
    buyer_id: uuidSchema.optional(),
    total_amount: nonNegativeNumberSchema.optional(),
    return_amount: nonNegativeNumberSchema.optional(),
    discount_amount: nonNegativeNumberSchema.optional(),
    sale_date: isoDateSchema.optional(),
    evidence_urls: z.array(z.string().url()).optional(),
  })
  .passthrough();

export const salesEventUpdateSchema = salesEventCreateSchema.partial();

export const revenueEventCreateSchema = z
  .object({
    location_id: uuidSchema.optional(),
    revenue_type: z.string().optional(),
    amount: nonNegativeNumberSchema.optional(),
    currency: z.string().min(3).max(3).optional(),
    revenue_date: isoDateSchema.optional(),
  })
  .passthrough();

export const revenueEventUpdateSchema = revenueEventCreateSchema.partial();

export function validateExpenseEventCreate(payload: Record<string, any>): Record<string, any> {
  return expenseEventCreateSchema.parse(payload);
}
export function validateExpenseEventUpdate(payload: Record<string, any>): Record<string, any> {
  return expenseEventUpdateSchema.parse(payload);
}
export function validateSalesEventCreate(payload: Record<string, any>): Record<string, any> {
  return salesEventCreateSchema.parse(payload);
}
export function validateSalesEventUpdate(payload: Record<string, any>): Record<string, any> {
  return salesEventUpdateSchema.parse(payload);
}
export function validateRevenueEventCreate(payload: Record<string, any>): Record<string, any> {
  return revenueEventCreateSchema.parse(payload);
}
export function validateRevenueEventUpdate(payload: Record<string, any>): Record<string, any> {
  return revenueEventUpdateSchema.parse(payload);
}
