/**
 * AI Helpers — Rule-based data cleaning and validation
 *
 * Auto-categorization, amount validation, quantity checks,
 * date validation, and field note summarization.
 * All logic is deterministic — no LLM calls.
 */

// ============================================================
// Expense auto-categorization
// ============================================================

const EXPENSE_KEYWORD_MAP: Record<string, { category: string; subcategory?: string }> = {
  seed: { category: 'seeds', subcategory: 'planting_material' },
  planting: { category: 'seeds', subcategory: 'planting_material' },
  fertilizer: { category: 'fertilizer', subcategory: 'chemical' },
  fertiliser: { category: 'fertilizer', subcategory: 'chemical' },
  compost: { category: 'fertilizer', subcategory: 'organic' },
  manure: { category: 'fertilizer', subcategory: 'organic' },
  lime: { category: 'fertilizer', subcategory: 'amendment' },
  pest: { category: 'pesticide', subcategory: 'insecticide' },
  herbicide: { category: 'pesticide', subcategory: 'herbicide' },
  fungicide: { category: 'pesticide', subcategory: 'fungicide' },
  spray: { category: 'pesticide', subcategory: 'general' },
  irrigation: { category: 'irrigation' },
  water: { category: 'irrigation' },
  pump: { category: 'irrigation', subcategory: 'equipment' },
  labor: { category: 'labor' },
  wages: { category: 'labor' },
  worker: { category: 'labor' },
  salary: { category: 'labor' },
  tractor: { category: 'equipment' },
  implement: { category: 'equipment' },
  tool: { category: 'equipment' },
  machinery: { category: 'equipment' },
  diesel: { category: 'equipment', subcategory: 'fuel' },
  fuel: { category: 'equipment', subcategory: 'fuel' },
  transport: { category: 'transport' },
  truck: { category: 'transport' },
  delivery: { category: 'transport' },
  logistics: { category: 'transport' },
  packaging: { category: 'processing' },
  bag: { category: 'processing', subcategory: 'materials' },
  box: { category: 'processing', subcategory: 'materials' },
  crate: { category: 'processing', subcategory: 'materials' },
  processing: { category: 'processing' },
  electricity: { category: 'utilities' },
  power: { category: 'utilities' },
  rent: { category: 'rent' },
  lease: { category: 'rent' },
  land: { category: 'rent' },
  insurance: { category: 'insurance' },
  marketing: { category: 'marketing' },
  advertising: { category: 'marketing' },
  consultant: { category: 'other' },
  service: { category: 'other' },
};

/**
 * Auto-categorize expense based on description text
 * Returns suggested category/subcategory or null if no match
 */
export function suggestExpenseCategory(
  description: string | undefined
): { category: string; subcategory?: string } | null {
  if (!description) return null;

  const lower = description.toLowerCase();
  const words = lower.split(/\s+/);

  // Score each keyword match
  let bestMatch: { category: string; subcategory?: string } | null = null;
  let bestScore = 0;

  for (const word of words) {
    for (const [keyword, mapping] of Object.entries(EXPENSE_KEYWORD_MAP)) {
      if (word.includes(keyword) || keyword.includes(word)) {
        const score = keyword.length; // longer matches score higher
        if (score > bestScore) {
          bestScore = score;
          bestMatch = mapping;
        }
      }
    }
  }

  return bestMatch;
}

/**
 * Apply expense auto-categorization to payload
 */
export function autoCategorizeExpense(payload: Record<string, any>): Record<string, any> {
  if (payload.category && payload.category !== '') return payload;

  const suggestion = suggestExpenseCategory(payload.description || payload.notes);
  if (suggestion) {
    payload.category = suggestion.category;
    if (suggestion.subcategory) {
      payload.subcategory = suggestion.subcategory;
    }
  }

  return payload;
}

// ============================================================
// Amount validation
// ============================================================

const AMOUNT_THRESHOLDS = {
  maxExpense: 100000,
  maxSale: 500000,
  maxHarvestQty: 100000,
  negativeNotAllowed: true,
  futureDateAllowed: false,
};

/**
 * Validate expense amount
 * Returns validation errors or empty array
 */
export function validateExpenseAmount(amount: number): string[] {
  const errors: string[] = [];

  if (amount === undefined || amount === null) {
    errors.push('Amount is required');
    return errors;
  }

  if (typeof amount !== 'number' || isNaN(amount)) {
    errors.push('Amount must be a number');
    return errors;
  }

  if (AMOUNT_THRESHOLDS.negativeNotAllowed && amount <= 0) {
    errors.push('Amount must be greater than zero');
  }

  if (amount > AMOUNT_THRESHOLDS.maxExpense) {
    errors.push(`Amount exceeds maximum threshold of $${AMOUNT_THRESHOLDS.maxExpense.toLocaleString()}`);
  }

  return errors;
}

/**
 * Validate sales amount
 */
export function validateSalesAmount(totalAmount: number): string[] {
  const errors: string[] = [];

  if (totalAmount === undefined || totalAmount === null) {
    errors.push('Total amount is required');
    return errors;
  }

  if (typeof totalAmount !== 'number' || isNaN(totalAmount)) {
    errors.push('Total amount must be a number');
    return errors;
  }

  if (totalAmount <= 0) {
    errors.push('Total amount must be greater than zero');
  }

  if (totalAmount > AMOUNT_THRESHOLDS.maxSale) {
    errors.push(`Total amount exceeds maximum threshold of $${AMOUNT_THRESHOLDS.maxSale.toLocaleString()}`);
  }

  return errors;
}

// ============================================================
// Harvest quantity validation
// ============================================================

/**
 * Validate harvest quantity against expected yield
 * Returns warnings (not errors) for unusual values
 */
export function validateHarvestQuantity(
  quantity: number,
  expectedYield?: number
): string[] {
  const warnings: string[] = [];

  if (quantity <= 0) {
    warnings.push('Harvest quantity must be greater than zero');
  }

  if (quantity > AMOUNT_THRESHOLDS.maxHarvestQty) {
    warnings.push(`Harvest quantity ${quantity} seems unusually high`);
  }

  if (expectedYield && expectedYield > 0) {
    const ratio = quantity / expectedYield;
    if (ratio > 1.5) {
      warnings.push(`Harvest quantity is ${Math.round(ratio * 100)}% of expected yield — please verify`);
    }
    if (ratio < 0.1 && quantity > 0) {
      warnings.push(`Harvest quantity is only ${Math.round(ratio * 100)}% of expected yield — possible data entry error`);
    }
  }

  return warnings;
}

// ============================================================
// Auto-calculate derived fields
// ============================================================

/**
 * Auto-calculate loss_estimated_value from loss_amount and crop price
 */
export function autoCalculateLossValue(
  lossAmount: number | undefined,
  lossUnit: string | undefined,
  quantity: number | undefined,
  totalAmount: number | undefined
): number | undefined {
  if (!lossAmount || !quantity || !totalAmount) return undefined;
  if (quantity === 0) return undefined;

  const pricePerUnit = totalAmount / quantity;
  return Math.round(lossAmount * pricePerUnit * 100) / 100;
}

/**
 * Auto-calculate net_amount for sales
 */
export function calculateNetAmount(
  totalAmount: number,
  returnAmount: number = 0,
  discountAmount: number = 0
): number {
  const net = totalAmount - returnAmount - discountAmount;
  return Math.max(0, net);
}

/**
 * Auto-calculate total_cost for labor
 */
export function calculateLaborCost(
  hoursWorked: number,
  hourlyRate: number
): number {
  return Math.round(hoursWorked * hourlyRate * 100) / 100;
}

// ============================================================
// Date validation
// ============================================================

/**
 * Validate that a date is not in the future
 * Returns validation error or null
 */
export function validateNotFutureDate(dateStr: string): string | null {
  if (AMOUNT_THRESHOLDS.futureDateAllowed) return null;

  const date = new Date(dateStr);
  const today = new Date();
  today.setHours(23, 59, 59, 999);

  if (date > today) {
    return `Date ${dateStr} is in the future — please verify`;
  }

  return null;
}

/**
 * Validate that expense_date is reasonable (not more than 1 year ago)
 */
export function validateExpenseDate(dateStr: string): string | null {
  const date = new Date(dateStr);
  const oneYearAgo = new Date();
  oneYearAgo.setFullYear(oneYearAgo.getFullYear() - 1);

  if (date < oneYearAgo) {
    return `Expense date ${dateStr} is more than 1 year ago — please verify`;
  }

  return validateNotFutureDate(dateStr);
}

// ============================================================
// Field note summarization
// ============================================================

/**
 * Extract first sentence as summary from field note content
 */
export function summarizeFieldNote(content: string): string {
  if (!content) return '';

  // Try to find first sentence (ends with . ! ?)
  const sentenceEnd = content.search(/[.!?]\s/);
  if (sentenceEnd > 0 && sentenceEnd < 300) {
    return content.substring(0, sentenceEnd + 1).trim();
  }

  // If no sentence boundary found, truncate at word boundary
  if (content.length > 200) {
    const truncated = content.substring(0, 200);
    const lastSpace = truncated.lastIndexOf(' ');
    return (lastSpace > 0 ? truncated.substring(0, lastSpace) : truncated) + '...';
  }

  return content;
}

/**
 * Auto-set field note summary if content is long
 */
export function autoSummarizeFieldNote(payload: Record<string, any>): Record<string, any> {
  if (payload.summary) return payload; // Already has summary

  const content = payload.content || '';
  if (content.length > 200) {
    payload.summary = summarizeFieldNote(content);
  }

  return payload;
}
