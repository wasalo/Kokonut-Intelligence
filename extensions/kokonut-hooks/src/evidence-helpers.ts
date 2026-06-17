/**
 * Evidence Helpers — File upload validation and processing
 *
 * Validates file type, size, and links uploaded files to parent records.
 */

// ============================================================
// Evidence file validation
// ============================================================

const ALLOWED_EVIDENCE_TYPES = new Set([
  'image/jpeg',
  'image/png',
  'image/webp',
  'image/heic',
  'image/heif',
  'application/pdf',
  'text/plain',
  'text/csv',
]);

const MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024; // 50MB
const MAX_EVIDENCE_URLS = 10;

/**
 * Validate evidence_urls array
 * Returns validation errors or empty array
 */
export function validateEvidenceUrls(urls: any): string[] {
  const errors: string[] = [];

  if (!urls) return errors;

  const arr = Array.isArray(urls) ? urls : [urls];

  if (arr.length > MAX_EVIDENCE_URLS) {
    errors.push(`Maximum ${MAX_EVIDENCE_URLS} evidence files allowed`);
  }

  for (const url of arr) {
    if (typeof url !== 'string') {
      errors.push('Evidence URL must be a string');
      continue;
    }
    if (url.length > 2048) {
      errors.push('Evidence URL too long (max 2048 chars)');
    }
  }

  return errors;
}

/**
 * Validate file metadata before upload
 * Returns validation errors or empty array
 */
export function validateFileUpload(payload: Record<string, any>): string[] {
  const errors: string[] = [];

  if (payload.filename && payload.filename.length > 255) {
    errors.push('Filename too long (max 255 chars)');
  }

  if (payload.file_size_bytes !== undefined) {
    if (typeof payload.file_size_bytes !== 'number' || payload.file_size_bytes < 0) {
      errors.push('File size must be a non-negative number');
    }
    if (payload.file_size_bytes > MAX_FILE_SIZE_BYTES) {
      errors.push(`File size exceeds maximum of ${MAX_FILE_SIZE_BYTES / (1024 * 1024)}MB`);
    }
  }

  if (payload.mime_type && !ALLOWED_EVIDENCE_TYPES.has(payload.mime_type)) {
    errors.push(`File type "${payload.mime_type}" not allowed. Allowed: ${[...ALLOWED_EVIDENCE_TYPES].join(', ')}`);
  }

  return errors;
}

/**
 * Validate image URLs in field_note.images
 * Returns validation errors or empty array
 */
export function validateFieldNoteImages(images: any): string[] {
  const errors: string[] = [];

  if (!images) return errors;

  const arr = Array.isArray(images) ? images : [images];

  if (arr.length > 20) {
    errors.push('Maximum 20 images allowed per field note');
  }

  for (const img of arr) {
    if (typeof img !== 'string') {
      errors.push('Image URL must be a string');
      continue;
    }
    if (img.length > 2048) {
      errors.push('Image URL too long (max 2048 chars)');
    }
    // Basic URL format check
    if (!img.startsWith('http://') && !img.startsWith('https://') && !img.startsWith('/')) {
      errors.push(`Invalid image URL format: ${img.substring(0, 50)}...`);
    }
  }

  return errors;
}
