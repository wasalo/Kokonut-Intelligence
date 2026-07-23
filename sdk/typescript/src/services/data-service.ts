/**
 * Typed wrapper for the gRPC DataService.
 *
 * Uses @grpc/proto-loader for runtime proto loading with generated
 * @bufbuild/protobuf types for compile-time type safety.
 */

import {
  Client,
  Metadata,
  credentials,
  type ChannelCredentials,
  type ServiceError,
} from "@grpc/grpc-js";
import * as protoLoader from "@grpc/proto-loader";
import path from "path";

import { KokonutGrpcError } from "../errors";

/** Options for constructing a DataServiceClient. */
export interface DataServiceClientOptions {
  credentials?: ChannelCredentials;
  metadata?: Metadata;
}

/** Thin typed wrapper around the raw gRPC DataService client. */
export class DataServiceClient {
  private readonly client: Client;
  private readonly defaultMetadata: Metadata;

  constructor(address: string, options: DataServiceClientOptions = {}) {
    const repoRoot = path.resolve(__dirname, "../../../../");
    const protoPath = path.resolve(repoRoot, "proto/data/v1/service.proto");
    const packageDefinition = protoLoader.loadSync(protoPath, {
      keepCase: true,
      longs: Number,
      enums: String,
      defaults: true,
      oneofs: true,
      includeDirs: [path.resolve(repoRoot, "proto")],
    });
    const grpc = require("@grpc/grpc-js");
    const ServiceDefinition = grpc.loadPackageDefinition(packageDefinition)
      .data?.v1?.DataService;
    if (!ServiceDefinition) {
      throw new Error("Failed to load DataService proto definition");
    }

    this.client = new ServiceDefinition(
      address,
      options.credentials ?? credentials.createInsecure(),
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

  resolveIRI(iri: string): Promise<{
    iri: string;
    entityType: string;
    entityId: string;
    version: number;
    contentHash: string;
  }> {
    return this._call("ResolveIRI", { iri });
  }

  getVersionHistory(entityType: string, entityId: string): Promise<{
    versions: Array<{
      iri: string;
      version: number;
      contentHash: string;
    }>;
  }> {
    return this._call("GetVersionHistory", {
      entity_type: entityType,
      entity_id: entityId,
    });
  }

  // ── Content Hash Operations ────────────────────────────────────────────

  computeContentHash(req: {
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
    return this._call("ComputeContentHash", {
      data: req.data,
      algorithm: req.algorithm ?? "sha256",
      content_type: req.contentType ?? "raw",
      media_type: req.mediaType ?? "",
    });
  }

  createContentHash(req: {
    iriId: string;
    hashValue: string;
    hashAlgorithm?: string;
    contentType?: string;
    mediaType?: string;
    canonicalizationAlgorithm?: string;
    merkleTree?: string;
  }): Promise<{ id: string; hashValue: string }> {
    return this._call("CreateContentHash", {
      iri_id: req.iriId,
      hash_value: req.hashValue,
      hash_algorithm: req.hashAlgorithm ?? "sha256",
      content_type: req.contentType ?? "raw",
      media_type: req.mediaType ?? "",
      canonicalization_algorithm: req.canonicalizationAlgorithm ?? "",
      merkle_tree: req.merkleTree ?? "none",
    });
  }

  findIRIByHash(hashValue: string): Promise<{
    results: Array<{
      iri: string;
      entityType: string;
      entityId: string;
      contentHash: string;
      hashAlgorithm: string;
    }>;
  }> {
    return this._call("FindIRIByHash", { hash_value: hashValue });
  }

  // ── Resolver Operations ────────────────────────────────────────────────

  defineResolver(req: {
    resolverUrl: string;
    managerAddress: string;
    description?: string;
  }): Promise<{ id: string; resolverUrl: string }> {
    return this._call("DefineResolver", {
      resolver_url: req.resolverUrl,
      manager_address: req.managerAddress,
      description: req.description ?? "",
    });
  }

  registerToResolver(req: {
    resolverId: string;
    iriId: string;
    registeredBy?: string;
  }): Promise<{ resolverId: string; iriId: string }> {
    return this._call("RegisterToResolver", {
      resolver_id: req.resolverId,
      iri_id: req.iriId,
      registered_by: req.registeredBy ?? "",
    });
  }

  getResolversForIRI(iriId: string): Promise<{
    resolvers: Array<{
      id: string;
      resolverUrl: string;
      managerAddress: string;
      isActive: boolean;
    }>;
  }> {
    return this._call("GetResolversForIRI", { iri_id: iriId });
  }

  listResolvers(managerAddress?: string): Promise<{
    resolvers: Array<{
      id: string;
      resolverUrl: string;
      managerAddress: string;
      isActive: boolean;
    }>;
  }> {
    return this._call("ListResolvers", {
      manager_address: managerAddress ?? "",
    });
  }

  // ── Attestor Operations ────────────────────────────────────────────────

  attestToIRI(req: {
    iriId: string;
    attestorAddress: string;
  }): Promise<{
    id: string;
    iriId: string;
    attestorAddress: string;
    alreadyAttested: boolean;
  }> {
    return this._call("AttestToIRI", {
      iri_id: req.iriId,
      attestor_address: req.attestorAddress,
    });
  }

  getAttestorsForIRI(iriId: string): Promise<{
    attestors: Array<{
      id: string;
      iriId: string;
      attestorAddress: string;
      attestedAt: number;
    }>;
  }> {
    return this._call("GetAttestorsForIRI", { iri_id: iriId });
  }

  // ── Streaming ──────────────────────────────────────────────────────────

  streamNewIRIs(
    entityType?: string,
  ): AsyncIterable<{
    iri: string;
    entityType: string;
    entityId: string;
    version: number;
    contentHash: string;
    timestamp: number;
  }> {
    const call = (this.client as any).StreamNewIRIs(
      { entity_type: entityType ?? "" },
      this.defaultMetadata,
    );
    return {
      [Symbol.asyncIterator]() {
        return {
          next(): Promise<IteratorResult<any>> {
            return new Promise((resolve, reject) => {
              call.on("data", (data: any) =>
                resolve({ value: data, done: false }),
              );
              call.on("end", () => resolve({ value: undefined, done: true }));
              call.on("error", (err: ServiceError) =>
                reject(KokonutGrpcError.fromServiceError(err)),
              );
            });
          },
        };
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
