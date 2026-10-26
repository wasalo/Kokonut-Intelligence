export class KokonutError extends Error {
  readonly statusCode: number;
  readonly response: unknown;

  constructor(message: string, statusCode = 0, response?: unknown) {
    super(message);
    this.name = new.target.name;
    this.statusCode = statusCode;
    this.response = response;
  }
}

export class AuthenticationError extends KokonutError {}
export class ForbiddenError extends KokonutError {}
export class NotFoundError extends KokonutError {}
export class ValidationError extends KokonutError {}

type RecordValue = Record<string, unknown>;

function asRecord(value: unknown): RecordValue | undefined {
  return typeof value === 'object' && value !== null
    ? value as RecordValue
    : undefined;
}

/** Normalize the plain error envelope emitted by the pinned Directus SDK. */
export function normalizeDirectusError(error: unknown): Error {
  if (error instanceof KokonutError) return error;

  const details = asRecord(error);
  if (!details) {
    return error instanceof Error
      ? error
      : new KokonutError('Kokonut API request failed');
  }

  const response = details.response;
  const responseDetails = asRecord(response);
  const rawStatus = responseDetails?.status
    ?? details.statusCode
    ?? details.status_code
    ?? details.status;
  const statusCode = typeof rawStatus === 'number' && Number.isInteger(rawStatus)
    ? rawStatus
    : 0;
  const rawErrors = details.errors;
  const firstError = Array.isArray(rawErrors) ? asRecord(rawErrors[0]) : undefined;
  const candidateMessage = firstError?.message
    ?? (typeof rawErrors === 'string' ? rawErrors : undefined)
    ?? details.message;

  // Preserve native transport errors, which have no HTTP response envelope.
  if (!responseDetails && statusCode === 0 && rawErrors === undefined) {
    return error instanceof Error
      ? error
      : new KokonutError('Kokonut API request failed');
  }

  const message = typeof candidateMessage === 'string' && candidateMessage.trim()
    ? candidateMessage
    : statusCode > 0 ? `HTTP ${statusCode}` : 'Kokonut API request failed';
  const ErrorType = statusCode === 400 ? ValidationError
    : statusCode === 401 ? AuthenticationError
      : statusCode === 403 ? ForbiddenError
        : statusCode === 404 ? NotFoundError
          : KokonutError;

  return new ErrorType(message, statusCode, response);
}
