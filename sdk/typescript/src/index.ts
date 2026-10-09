/**
 * @kokonut/intelligence-client — TypeScript gRPC client for Kokonut Intelligence Platform.
 *
 * @example
 * ```ts
 * import { KokonutGrpcClient } from "@kokonut/intelligence-client";
 *
 * const client = new KokonutGrpcClient("localhost:50051");
 * const data = client.data;
 * const ecocredit = client.ecocredit;
 *
 * // Generate an IRI
 * const { iri } = await data.generateIRI({
 *   entityType: "location",
 *   entityId: "loc-001",
 * });
 *
 * // List credit classes
 * const { classes } = await ecocredit.classes();
 *
 * client.close();
 * ```
 */

import {
  Client,
  credentials,
  type ChannelCredentials,
} from "@grpc/grpc-js";

import {
  KokonutGrpcError,
  NotFoundError,
  PermissionDeniedError,
  UnauthenticatedError,
  InvalidArgumentError,
  InternalError,
  UnavailableError,
} from "./errors";

import {
  DataServiceClient,
  type DataServiceClientOptions,
} from "./services/data-service";

import {
  EcocreditServiceClient,
  type EcocreditServiceClientOptions,
} from "./services/ecocredit-service";

/** Top-level options for KokonutGrpcClient. */
export interface KokonutClientOptions {
  credentials?: ChannelCredentials;
  metadata?: import("@grpc/grpc-js").Metadata;
}

/**
 * Shared gRPC transport for Kokonut Intelligence services.
 *
 * Provides typed accessors for DataService and EcocreditService.
 */
export class KokonutGrpcClient {
  public readonly transport: Client;
  public readonly data: DataServiceClient;
  public readonly ecocredit: EcocreditServiceClient;

  constructor(address: string, options: KokonutClientOptions = {}) {
    this.transport = new Client(
      address,
      options.credentials ?? credentials.createInsecure(),
    );

    const svcOpts: DataServiceClientOptions & EcocreditServiceClientOptions =
      {
        credentials: options.credentials,
        metadata: options.metadata,
      };

    this.data = new DataServiceClient(address, svcOpts);
    this.ecocredit = new EcocreditServiceClient(address, svcOpts);
  }

  close(): void {
    this.data.close();
    this.ecocredit.close();
    this.transport.close();
  }
}

// ── Re-exports ──────────────────────────────────────────────────────────

export { DataServiceClient } from "./services/data-service";
export { EcocreditServiceClient } from "./services/ecocredit-service";
export type { DataServiceClientOptions } from "./services/data-service";
export type { EcocreditServiceClientOptions } from "./services/ecocredit-service";

export {
  KokonutGrpcError,
  NotFoundError,
  PermissionDeniedError,
  UnauthenticatedError,
  InvalidArgumentError,
  InternalError,
  UnavailableError,
} from "./errors";
