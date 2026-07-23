import { ServiceError } from "@grpc/grpc-js";

/** Base error for all Kokonut gRPC client errors. */
export class KokonutGrpcError extends Error {
  readonly code: number;
  readonly details: string;
  readonly metadata: Record<string, string>;

  constructor(
    message: string,
    code: number,
    details: string = "",
    metadata: Record<string, string> = {},
  ) {
    super(message);
    this.name = "KokonutGrpcError";
    this.code = code;
    this.details = details;
    this.metadata = metadata;
  }

  static fromServiceError(err: ServiceError): KokonutGrpcError {
    const metadata: Record<string, string> = {};
    if (err.metadata) {
      for (const [k, v] of Object.entries(err.metadata.getMap())) {
        if (typeof v === "string") metadata[k] = v;
      }
    }

    const mapping: Record<number, typeof KokonutGrpcError> = {
      5: NotFoundError,
      7: PermissionDeniedError,
      16: UnauthenticatedError,
      3: InvalidArgumentError,
      13: InternalError,
      14: UnavailableError,
    };

    const Klass = mapping[err.code] ?? KokonutGrpcError;
    return new Klass(
      `gRPC ${err.code}: ${err.message}`,
      err.code,
      err.details,
      metadata,
    );
  }
}

/** NOT_FOUND (5) — requested resource does not exist. */
export class NotFoundError extends KokonutGrpcError {
  constructor(message: string, code = 5, details = "", metadata = {}) {
    super(message, code, details, metadata);
    this.name = "NotFoundError";
  }
}

/** PERMISSION_DENIED (7) — caller lacks required permissions. */
export class PermissionDeniedError extends KokonutGrpcError {
  constructor(message: string, code = 7, details = "", metadata = {}) {
    super(message, code, details, metadata);
    this.name = "PermissionDeniedError";
  }
}

/** UNAUTHENTICATED (16) — missing or invalid credentials. */
export class UnauthenticatedError extends KokonutGrpcError {
  constructor(message: string, code = 16, details = "", metadata = {}) {
    super(message, code, details, metadata);
    this.name = "UnauthenticatedError";
  }
}

/** INVALID_ARGUMENT (3) — malformed request. */
export class InvalidArgumentError extends KokonutGrpcError {
  constructor(message: string, code = 3, details = "", metadata = {}) {
    super(message, code, details, metadata);
    this.name = "InvalidArgumentError";
  }
}

/** INTERNAL (13) — server-side error. */
export class InternalError extends KokonutGrpcError {
  constructor(message: string, code = 13, details = "", metadata = {}) {
    super(message, code, details, metadata);
    this.name = "InternalError";
  }
}

/** UNAVAILABLE (14) — server is unreachable or shutting down. */
export class UnavailableError extends KokonutGrpcError {
  constructor(message: string, code = 14, details = "", metadata = {}) {
    super(message, code, details, metadata);
    this.name = "UnavailableError";
  }
}
