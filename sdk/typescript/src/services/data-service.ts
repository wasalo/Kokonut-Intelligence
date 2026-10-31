/**
 * Typed wrapper for the gRPC DataService.
 *
 * Loads the package-bundled proto source with @grpc/proto-loader.
 */

import {
  Client,
  Metadata,
  type ChannelCredentials,
  type ServiceError,
} from "@grpc/grpc-js";
import { existsSync } from "fs";
import * as protoLoader from "@grpc/proto-loader";
import path from "path";

import { KokonutGrpcError } from "../errors";
import { resolveChannelCredentials } from "../transport";

/** Options for constructing a DataServiceClient. */
export interface DataServiceClientOptions {
  credentials?: ChannelCredentials;
  metadata?: Metadata;
}

function responseRecord(value: unknown, method: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`Invalid ${method} response: expected an object`);
  }
  return value as Record<string, unknown>;
}

function responseString(
  record: Record<string, unknown>,
  field: string,
  method: string,
): string {
  const value = record[field];
  if (typeof value !== "string") {
    throw new Error(`Invalid ${method} response: ${field} must be a string`);
  }
  return value;
}

function responseNumber(
  record: Record<string, unknown>,
  field: string,
  method: string,
): number {
  const value = record[field];
  if (typeof value !== "number" || !Number.isSafeInteger(value)) {
    throw new Error(`Invalid ${method} response: ${field} must be an integer`);
  }
  return value;
}

function responseInt32(
  record: Record<string, unknown>,
  field: string,
  method: string,
): number {
  const value = record[field];
  if (
    typeof value !== "number" ||
    !Number.isInteger(value) ||
    value < -2_147_483_648 ||
    value > 2_147_483_647
  ) {
    throw new Error(`Invalid ${method} response: ${field} must be an int32`);
  }
  return value;
}

function responseBoolean(
  record: Record<string, unknown>,
  field: string,
  method: string,
): boolean {
  const value = record[field];
  if (typeof value !== "boolean") {
    throw new Error(`Invalid ${method} response: ${field} must be a boolean`);
  }
  return value;
}

function responseArray(
  record: Record<string, unknown>,
  field: string,
  method: string,
): unknown[] {
  const value = record[field];
  if (!Array.isArray(value)) {
    throw new Error(`Invalid ${method} response: ${field} must be an array`);
  }
  return value;
}

type StreamUpdate = {
  iri: string;
  entityType: string;
  entityId: string;
  version: number;
  contentHash: string;
  timestamp: number;
};

function normalizeStreamUpdate(value: unknown): StreamUpdate {
  const update = responseRecord(value, "StreamNewIRIs");
  return {
    iri: responseString(update, "iri", "StreamNewIRIs"),
    entityType: responseString(update, "entity_type", "StreamNewIRIs"),
    entityId: responseString(update, "entity_id", "StreamNewIRIs"),
    version: responseInt32(update, "version", "StreamNewIRIs"),
    contentHash: responseString(update, "content_hash", "StreamNewIRIs"),
    timestamp: responseNumber(update, "timestamp", "StreamNewIRIs"),
  };
}

/** Thin typed wrapper around the raw gRPC DataService client. */
export class DataServiceClient {
  private readonly client: Client;
  private readonly defaultMetadata: Metadata;

  constructor(address: string, options: DataServiceClientOptions = {}) {
    const bundledProtoRoot = path.resolve(__dirname, "../proto");
    const protoRoot = existsSync(bundledProtoRoot)
      ? bundledProtoRoot
      : path.resolve(__dirname, "../../../../proto");
    const protoPath = path.resolve(protoRoot, "data/v1/service.proto");
    const packageDefinition = protoLoader.loadSync(protoPath, {
      keepCase: true,
      longs: Number,
      enums: String,
      defaults: true,
      oneofs: true,
      includeDirs: [protoRoot],
    });
    const grpc = require("@grpc/grpc-js");
    const ServiceDefinition = grpc.loadPackageDefinition(packageDefinition)
      .data?.v1?.DataService;
    if (!ServiceDefinition) {
      throw new Error("Failed to load DataService proto definition");
    }

    this.client = new ServiceDefinition(
      address,
      resolveChannelCredentials(address, options.credentials),
    ) as Client;
    this.defaultMetadata = options.metadata ?? new Metadata();
  }

  close(): void {
    this.client.close();
  }

  // ── IRI Operations ────────────────────────────────────────────────────

  generateIRI(req: {
    entityType: string;
    entityId: string;
    metadataJson?: string;
    contentHashType?: string;
    algorithm?: string;
  }): Promise<{ iri: string }> {
    return this._call("GenerateIRI", {
      entity_type: req.entityType,
      entity_id: req.entityId,
      metadata_json: req.metadataJson ?? "",
      content_hash_type: req.contentHashType ?? "",
      algorithm: req.algorithm ?? "",
    });
  }

  async resolveIRI(iri: string): Promise<{
    iri: string;
    entityType: string;
    entityId: string;
    version: number;
    contentHash: string;
  }> {
    const response = await this._call<{
      iri_info?: {
        iri?: unknown;
        entity_type?: unknown;
        entity_id?: unknown;
        version?: unknown;
        content_hash?: unknown;
      };
    }>("ResolveIRI", { iri });
    const info = response?.iri_info;
    if (
      !info ||
      typeof info.iri !== "string" ||
      typeof info.entity_type !== "string" ||
      typeof info.entity_id !== "string" ||
      typeof info.content_hash !== "string"
    ) {
      throw new Error("Invalid ResolveIRI response: expected an iri_info record");
    }
    const version = responseInt32(
      info as Record<string, unknown>,
      "version",
      "ResolveIRI",
    );

    return {
      iri: info.iri,
      entityType: info.entity_type,
      entityId: info.entity_id,
      version,
      contentHash: info.content_hash,
    };
  }

  async getVersionHistory(entityType: string, entityId: string): Promise<{
    versions: Array<{
      iri: string;
      version: number;
      contentHash: string;
    }>;
  }> {
    const response = await this._call<{ versions?: unknown }>("GetVersionHistory", {
      entity_type: entityType,
      entity_id: entityId,
    });
    if (!response || !Array.isArray(response.versions)) {
      throw new Error("Invalid GetVersionHistory response: expected a versions array");
    }

    return {
      versions: response.versions.map((version) => {
        if (!version || typeof version !== "object" || Array.isArray(version)) {
          throw new Error("Invalid GetVersionHistory response: malformed version entry");
        }
        const entry = version as Record<string, unknown>;
        if (
          typeof entry.iri !== "string" ||
          typeof entry.content_hash !== "string"
        ) {
          throw new Error("Invalid GetVersionHistory response: malformed version entry");
        }
        return {
          iri: entry.iri,
          version: responseInt32(entry, "version", "GetVersionHistory"),
          contentHash: entry.content_hash,
        };
      }),
    };
  }

  // ── Content Hash Operations ────────────────────────────────────────────

  async computeContentHash(req: {
    data: string;
    algorithm?: string;
    contentType?: string;
    mediaType?: string;
  }): Promise<{
    hashValue: string;
    hashAlgorithm: string;
    contentType: string;
    mediaType: string;
  }> {
    const response = await this._call<{
      hash_value?: unknown;
      hash_algorithm?: unknown;
      content_type?: unknown;
      media_type?: unknown;
    }>("ComputeContentHash", {
      data: req.data,
      algorithm: req.algorithm ?? "sha256",
      content_type: req.contentType ?? "raw",
      media_type: req.mediaType ?? "",
    });
    if (
      !response ||
      typeof response.hash_value !== "string" ||
      typeof response.hash_algorithm !== "string" ||
      typeof response.content_type !== "string" ||
      typeof response.media_type !== "string"
    ) {
      throw new Error(
        "Invalid ComputeContentHash response: expected hash and content metadata",
      );
    }

    return {
      hashValue: response.hash_value,
      hashAlgorithm: response.hash_algorithm,
      contentType: response.content_type,
      mediaType: response.media_type,
    };
  }

  async createContentHash(req: {
    iriId: string;
    hashValue: string;
    hashAlgorithm?: string;
    contentType?: string;
    mediaType?: string;
    canonicalizationAlgorithm?: string;
    merkleTree?: string;
  }): Promise<{ id: string; hashValue: string }> {
    const response = responseRecord(
      await this._call("CreateContentHash", {
        iri_id: req.iriId,
        hash_value: req.hashValue,
        hash_algorithm: req.hashAlgorithm ?? "sha256",
        content_type: req.contentType ?? "raw",
        media_type: req.mediaType ?? "",
        canonicalization_algorithm: req.canonicalizationAlgorithm ?? "",
        merkle_tree: req.merkleTree ?? "none",
      }),
      "CreateContentHash",
    );
    return {
      id: responseString(response, "id", "CreateContentHash"),
      hashValue: responseString(response, "hash_value", "CreateContentHash"),
    };
  }

  async findIRIByHash(hashValue: string): Promise<{
    results: Array<{
      iri: string;
      entityType: string;
      entityId: string;
      contentHash: string;
      hashAlgorithm: string;
    }>;
  }> {
    const response = responseRecord(
      await this._call("FindIRIByHash", { hash_value: hashValue }),
      "FindIRIByHash",
    );
    const results = responseArray(response, "results", "FindIRIByHash");
    return {
      results: results.map((result) => {
        const entry = responseRecord(result, "FindIRIByHash");
        return {
          iri: responseString(entry, "iri", "FindIRIByHash"),
          entityType: responseString(entry, "entity_type", "FindIRIByHash"),
          entityId: responseString(entry, "entity_id", "FindIRIByHash"),
          contentHash: responseString(entry, "content_hash", "FindIRIByHash"),
          hashAlgorithm: responseString(entry, "hash_algorithm", "FindIRIByHash"),
        };
      }),
    };
  }

  // ── Resolver Operations ────────────────────────────────────────────────

  async defineResolver(req: {
    resolverUrl: string;
    managerAddress: string;
    description?: string;
  }): Promise<{ id: string; resolverUrl: string }> {
    const response = responseRecord(
      await this._call("DefineResolver", {
        resolver_url: req.resolverUrl,
        manager_address: req.managerAddress,
        description: req.description ?? "",
      }),
      "DefineResolver",
    );
    return {
      id: responseString(response, "id", "DefineResolver"),
      resolverUrl: responseString(response, "resolver_url", "DefineResolver"),
    };
  }

  async registerToResolver(req: {
    resolverId: string;
    iriId: string;
    registeredBy?: string;
  }): Promise<{ resolverId: string; iriId: string }> {
    const response = responseRecord(
      await this._call("RegisterToResolver", {
        resolver_id: req.resolverId,
        iri_id: req.iriId,
        registered_by: req.registeredBy ?? "",
      }),
      "RegisterToResolver",
    );
    return {
      resolverId: responseString(response, "resolver_id", "RegisterToResolver"),
      iriId: responseString(response, "iri_id", "RegisterToResolver"),
    };
  }

  async getResolversForIRI(iriId: string): Promise<{
    resolvers: Array<{
      id: string;
      resolverUrl: string;
      managerAddress: string;
      isActive: boolean;
    }>;
  }> {
    const response = responseRecord(
      await this._call("GetResolversForIRI", { iri_id: iriId }),
      "GetResolversForIRI",
    );
    return {
      resolvers: responseArray(response, "resolvers", "GetResolversForIRI").map(
        (resolver) => {
          const entry = responseRecord(resolver, "GetResolversForIRI");
          return {
            id: responseString(entry, "id", "GetResolversForIRI"),
            resolverUrl: responseString(entry, "resolver_url", "GetResolversForIRI"),
            managerAddress: responseString(entry, "manager_address", "GetResolversForIRI"),
            isActive: responseBoolean(entry, "is_active", "GetResolversForIRI"),
          };
        },
      ),
    };
  }

  async listResolvers(managerAddress?: string): Promise<{
    resolvers: Array<{
      id: string;
      resolverUrl: string;
      managerAddress: string;
      isActive: boolean;
    }>;
  }> {
    const response = responseRecord(
      await this._call("ListResolvers", {
        manager_address: managerAddress ?? "",
      }),
      "ListResolvers",
    );
    return {
      resolvers: responseArray(response, "resolvers", "ListResolvers").map(
        (resolver) => {
          const entry = responseRecord(resolver, "ListResolvers");
          return {
            id: responseString(entry, "id", "ListResolvers"),
            resolverUrl: responseString(entry, "resolver_url", "ListResolvers"),
            managerAddress: responseString(entry, "manager_address", "ListResolvers"),
            isActive: responseBoolean(entry, "is_active", "ListResolvers"),
          };
        },
      ),
    };
  }

  // ── Attestor Operations ────────────────────────────────────────────────

  async attestToIRI(req: {
    iriId: string;
    attestorAddress: string;
  }): Promise<{
    id: string;
    iriId: string;
    attestorAddress: string;
    alreadyAttested: boolean;
  }> {
    const response = responseRecord(
      await this._call("AttestToIRI", {
        iri_id: req.iriId,
        attestor_address: req.attestorAddress,
      }),
      "AttestToIRI",
    );
    return {
      id: responseString(response, "id", "AttestToIRI"),
      iriId: responseString(response, "iri_id", "AttestToIRI"),
      attestorAddress: responseString(response, "attestor_address", "AttestToIRI"),
      alreadyAttested: responseBoolean(response, "already_attested", "AttestToIRI"),
    };
  }

  async getAttestorsForIRI(iriId: string): Promise<{
    attestors: Array<{
      id: string;
      iriId: string;
      attestorAddress: string;
      attestedAt: number;
    }>;
  }> {
    const response = responseRecord(
      await this._call("GetAttestorsForIRI", { iri_id: iriId }),
      "GetAttestorsForIRI",
    );
    return {
      attestors: responseArray(response, "attestors", "GetAttestorsForIRI").map(
        (attestor) => {
          const entry = responseRecord(attestor, "GetAttestorsForIRI");
          return {
            id: responseString(entry, "id", "GetAttestorsForIRI"),
            iriId: responseString(entry, "iri_id", "GetAttestorsForIRI"),
            attestorAddress: responseString(entry, "attestor_address", "GetAttestorsForIRI"),
            attestedAt: responseNumber(entry, "attested_at", "GetAttestorsForIRI"),
          };
        },
      ),
    };
  }

  // ── Streaming ──────────────────────────────────────────────────────────

  streamNewIRIs(
    entityType?: string,
  ): AsyncIterable<StreamUpdate> {
    const call: any = (this.client as any).StreamNewIRIs(
      { entity_type: entityType ?? "" },
      this.defaultMetadata,
    );
    const queueHighWaterMark = 32;
    const queueLowWaterMark = 16;
    const queued: StreamUpdate[] = [];
    const waiters: Array<{
      resolve: (value: IteratorResult<StreamUpdate>) => void;
      reject: (reason: Error) => void;
    }> = [];
    let ended = false;
    let locallyCancelled = false;
    let paused = false;
    let failure: Error | undefined;

    const cleanupDataListeners = () => {
      call.removeListener("data", onData);
      call.removeListener("end", onEnd);
    };

    const cleanup = () => {
      cleanupDataListeners();
      call.removeListener("error", onError);
      call.removeListener("close", onClose);
    };

    const settleEnd = () => {
      if (ended) return;
      ended = true;
      cleanupDataListeners();
      while (waiters.length > 0) {
        waiters.shift()?.resolve({ value: undefined, done: true });
      }
    };

    const settleFailure = (error: Error) => {
      if (ended) return;
      failure = error;
      ended = true;
      cleanupDataListeners();
      while (waiters.length > 0) {
        waiters.shift()?.reject(error);
      }
    };

    const onData = (data: unknown) => {
      let update: StreamUpdate;
      try {
        update = normalizeStreamUpdate(data);
      } catch (error) {
        const malformed =
          error instanceof Error
            ? error
            : new Error("Invalid StreamNewIRIs response");
        settleFailure(malformed);
        locallyCancelled = true;
        call.cancel();
        return;
      }

      const waiter = waiters.shift();
      if (waiter) {
        waiter.resolve({ value: update, done: false });
      } else {
        queued.push(update);
        if (!paused && queued.length >= queueHighWaterMark) {
          call.pause();
          paused = true;
        }
      }
    };

    const onEnd = () => settleEnd();
    const onError = (error: ServiceError) => {
      if (locallyCancelled && error.code === 1) {
        cleanup();
        return;
      }

      const grpcError = KokonutGrpcError.fromServiceError(error);
      if (ended && locallyCancelled) {
        failure = grpcError;
      } else {
        settleFailure(grpcError);
      }
      cleanup();
    };
    const onClose = () => {
      if (!ended) {
        if (locallyCancelled) {
          settleEnd();
        } else {
          settleFailure(new Error("StreamNewIRIs closed before end"));
        }
      }
      cleanup();
    };

    call.on("data", onData);
    call.on("end", onEnd);
    call.on("error", onError);
    call.on("close", onClose);

    const iterator: AsyncIterator<StreamUpdate> = {
      next(): Promise<IteratorResult<StreamUpdate>> {
        const value = queued.shift();
        if (value !== undefined) {
          if (paused && queued.length <= queueLowWaterMark) {
            paused = false;
            call.resume();
          }
          return Promise.resolve({ value, done: false });
        }
        if (failure) return Promise.reject(failure);
        if (ended) return Promise.resolve({ value: undefined, done: true });
        return new Promise((resolve, reject) => waiters.push({ resolve, reject }));
      },
      return(): Promise<IteratorResult<StreamUpdate>> {
        if (!ended) {
          locallyCancelled = true;
          queued.length = 0;
          settleEnd();
          call.cancel();
        }
        return Promise.resolve({ value: undefined, done: true });
      },
    };

    return {
      [Symbol.asyncIterator]() {
        return iterator;
      },
    };
  }

  // ── Internal ───────────────────────────────────────────────────────────

  private _call<T>(method: string, request: any): Promise<T> {
    return new Promise((resolve, reject) => {
      (this.client as any)[method](
        request,
        this.defaultMetadata,
        (err: ServiceError | null, response: T) => {
          if (err) {
            reject(KokonutGrpcError.fromServiceError(err));
          } else {
            resolve(response);
          }
        },
      );
    });
  }
}
