import { EventEmitter } from "node:events";
import { describe, it, expect, vi } from "vitest";

type RpcCallback = (error: Error | null, response: unknown) => void;

function unaryResponse(response: unknown) {
  return (
    _request: unknown,
    _metadata: unknown,
    callback: RpcCallback,
  ) => callback(null, response);
}

function fakeReadableStream() {
  const stream = new EventEmitter() as EventEmitter & {
    cancel: ReturnType<typeof vi.fn>;
    pause: ReturnType<typeof vi.fn>;
    resume: ReturnType<typeof vi.fn>;
  };
  stream.pause = vi.fn();
  stream.resume = vi.fn();
  stream.cancel = vi.fn(() => {
    stream.emit(
      "error",
      Object.assign(new Error("cancelled"), { code: 1, details: "cancelled" }),
    );
  });
  return stream;
}

async function dataClientWithResponses(responses: Record<string, unknown>) {
  const { DataServiceClient } = await import("../services/data-service");
  const client = Object.create(DataServiceClient.prototype) as InstanceType<
    typeof DataServiceClient
  >;
  const rpcClient = Object.fromEntries(
    Object.entries(responses).map(([method, response]) => [
      method,
      unaryResponse(response),
    ]),
  );
  Object.assign(client, { client: rpcClient, defaultMetadata: {} });
  return client;
}

describe("KokonutGrpcClient", () => {
  it("exports all error classes", async () => {
    const mod = await import("../index");
    expect(mod.KokonutGrpcError).toBeDefined();
    expect(mod.NotFoundError).toBeDefined();
    expect(mod.PermissionDeniedError).toBeDefined();
    expect(mod.UnauthenticatedError).toBeDefined();
    expect(mod.InvalidArgumentError).toBeDefined();
    expect(mod.InternalError).toBeDefined();
    expect(mod.UnavailableError).toBeDefined();
  });

  it("exports service clients", async () => {
    const mod = await import("../index");
    expect(mod.DataServiceClient).toBeDefined();
    expect(mod.EcocreditServiceClient).toBeDefined();
  });
});

describe("KokonutGrpcError", () => {
  it("wraps a gRPC status code and details", async () => {
    const { KokonutGrpcError } = await import("../errors");
    const err = new KokonutGrpcError("test", 5, "not found", {});
    expect(err.code).toBe(5);
    expect(err.details).toBe("not found");
    expect(err.name).toBe("KokonutGrpcError");
    expect(err).toBeInstanceOf(Error);
  });

  it("creates NotFoundError from code 5", async () => {
    const { NotFoundError } = await import("../errors");
    const err = new NotFoundError("missing");
    expect(err.code).toBe(5);
    expect(err.name).toBe("NotFoundError");
    expect(err).toBeInstanceOf(Error);
  });

  it("creates UnauthenticatedError from code 16", async () => {
    const { UnauthenticatedError } = await import("../errors");
    const err = new UnauthenticatedError("no auth");
    expect(err.code).toBe(16);
    expect(err.name).toBe("UnauthenticatedError");
  });
});

describe("DataServiceClient", () => {
  it("can be constructed with an address", async () => {
    const { DataServiceClient } = await import("../services/data-service");
    const client = new DataServiceClient("localhost:50051");
    expect(client).toBeDefined();
    expect(typeof client.close).toBe("function");
    expect(typeof client.generateIRI).toBe("function");
    expect(typeof client.resolveIRI).toBe("function");
    expect(typeof client.getVersionHistory).toBe("function");
    expect(typeof client.computeContentHash).toBe("function");
    expect(typeof client.createContentHash).toBe("function");
    expect(typeof client.findIRIByHash).toBe("function");
    expect(typeof client.defineResolver).toBe("function");
    expect(typeof client.registerToResolver).toBe("function");
    expect(typeof client.getResolversForIRI).toBe("function");
    expect(typeof client.listResolvers).toBe("function");
    expect(typeof client.attestToIRI).toBe("function");
    expect(typeof client.getAttestorsForIRI).toBe("function");
    expect(typeof client.streamNewIRIs).toBe("function");
    client.close();
  });

  it("normalizes the nested ResolveIRI proto response to the declared SDK shape", async () => {
    const { DataServiceClient } = await import("../services/data-service");
    const client = Object.create(DataServiceClient.prototype) as DataServiceClient;
    Object.assign(client, {
      client: {
        ResolveIRI: (
          _request: unknown,
          _metadata: unknown,
          callback: (error: Error | null, response: unknown) => void,
        ) =>
          callback(null, {
            iri_info: {
              iri: "kokonut:location:adelphi:v1",
              entity_type: "location",
              entity_id: "adelphi",
              version: 1,
              content_hash: "sha256:example",
            },
          }),
      },
      defaultMetadata: {},
    });

    await expect(client.resolveIRI("kokonut:location:adelphi:v1")).resolves.toEqual({
      iri: "kokonut:location:adelphi:v1",
      entityType: "location",
      entityId: "adelphi",
      version: 1,
      contentHash: "sha256:example",
    });
  });

  it("rejects malformed nested ResolveIRI proto responses", async () => {
    const { DataServiceClient } = await import("../services/data-service");
    const client = Object.create(DataServiceClient.prototype) as DataServiceClient;
    Object.assign(client, {
      client: {
        ResolveIRI: (
          _request: unknown,
          _metadata: unknown,
          callback: (error: Error | null, response: unknown) => void,
        ) => callback(null, { iri_info: { iri: "kokonut:location:adelphi:v1" } }),
      },
      defaultMetadata: {},
    });

    await expect(client.resolveIRI("kokonut:location:adelphi:v1")).rejects.toThrow(
      "Invalid ResolveIRI response: expected an iri_info record",
    );
  });

  it.each([
    ["ResolveIRI", { iri_info: {
      iri: "kokonut:location:adelphi:v1",
      entity_type: "location",
      entity_id: "adelphi",
      version: 1.5,
      content_hash: "hash",
    } }, (client: any) => client.resolveIRI("kokonut:location:adelphi:v1")],
    ["GetVersionHistory", { versions: [{ iri: "iri", version: Number.NaN, content_hash: "hash" }] }, (client: any) => client.getVersionHistory("location", "adelphi")],
  ])("rejects non-int32 %s versions", async (_method, response, invoke) => {
    const client = await dataClientWithResponses({
      [String(_method)]: response,
    });

    await expect((invoke as (client: any) => Promise<unknown>)(client)).rejects.toThrow(
      `Invalid ${String(_method)} response: version must be an int32`,
    );
  });

  it("normalizes all DataService unary proto response fields", async () => {
    const client = await dataClientWithResponses({
      GetVersionHistory: {
        versions: [
          {
            iri: "kokonut:location:adelphi:v1",
            version: 1,
            content_hash: "sha256:version",
          },
        ],
      },
      ComputeContentHash: {
        hash_value: "sha256:value",
        hash_algorithm: "sha256",
        content_type: "raw",
        media_type: "text/plain",
      },
      CreateContentHash: { id: "entry-1", hash_value: "sha256:value" },
      FindIRIByHash: {
        results: [
          {
            iri: "kokonut:location:adelphi:v1",
            entity_type: "location",
            entity_id: "adelphi",
            content_hash: "sha256:value",
            hash_algorithm: "sha256",
          },
        ],
      },
      DefineResolver: { id: "resolver-1", resolver_url: "https://example.test" },
      RegisterToResolver: { resolver_id: "resolver-1", iri_id: "iri-1" },
      GetResolversForIRI: {
        resolvers: [
          {
            id: "resolver-1",
            resolver_url: "https://example.test",
            manager_address: "0x1234",
            is_active: true,
          },
        ],
      },
      ListResolvers: {
        resolvers: [
          {
            id: "resolver-2",
            resolver_url: "https://other.test",
            manager_address: "0xabcd",
            is_active: false,
          },
        ],
      },
      AttestToIRI: {
        id: "attestation-1",
        iri_id: "iri-1",
        attestor_address: "0x1234",
        already_attested: false,
      },
      GetAttestorsForIRI: {
        attestors: [
          {
            id: "attestation-1",
            iri_id: "iri-1",
            attestor_address: "0x1234",
            attested_at: 123,
          },
        ],
      },
    });

    await expect(client.getVersionHistory("location", "adelphi")).resolves.toEqual({
      versions: [
        {
          iri: "kokonut:location:adelphi:v1",
          version: 1,
          contentHash: "sha256:version",
        },
      ],
    });
    await expect(
      client.computeContentHash({ data: "example" }),
    ).resolves.toEqual({
      hashValue: "sha256:value",
      hashAlgorithm: "sha256",
      contentType: "raw",
      mediaType: "text/plain",
    });
    await expect(
      client.createContentHash({ iriId: "iri-1", hashValue: "sha256:value" }),
    ).resolves.toEqual({ id: "entry-1", hashValue: "sha256:value" });
    await expect(client.findIRIByHash("sha256:value")).resolves.toEqual({
      results: [
        {
          iri: "kokonut:location:adelphi:v1",
          entityType: "location",
          entityId: "adelphi",
          contentHash: "sha256:value",
          hashAlgorithm: "sha256",
        },
      ],
    });
    await expect(
      client.defineResolver({
        resolverUrl: "https://example.test",
        managerAddress: "0x1234",
      }),
    ).resolves.toEqual({ id: "resolver-1", resolverUrl: "https://example.test" });
    await expect(
      client.registerToResolver({ resolverId: "resolver-1", iriId: "iri-1" }),
    ).resolves.toEqual({ resolverId: "resolver-1", iriId: "iri-1" });
    await expect(client.getResolversForIRI("iri-1")).resolves.toEqual({
      resolvers: [
        {
          id: "resolver-1",
          resolverUrl: "https://example.test",
          managerAddress: "0x1234",
          isActive: true,
        },
      ],
    });
    await expect(client.listResolvers()).resolves.toEqual({
      resolvers: [
        {
          id: "resolver-2",
          resolverUrl: "https://other.test",
          managerAddress: "0xabcd",
          isActive: false,
        },
      ],
    });
    await expect(
      client.attestToIRI({ iriId: "iri-1", attestorAddress: "0x1234" }),
    ).resolves.toEqual({
      id: "attestation-1",
      iriId: "iri-1",
      attestorAddress: "0x1234",
      alreadyAttested: false,
    });
    await expect(client.getAttestorsForIRI("iri-1")).resolves.toEqual({
      attestors: [
        {
          id: "attestation-1",
          iriId: "iri-1",
          attestorAddress: "0x1234",
          attestedAt: 123,
        },
      ],
    });
  });

  it.each([
    ["GetVersionHistory", { versions: [{ iri: 3 }] }, (client: any) => client.getVersionHistory("location", "adelphi")],
    ["ComputeContentHash", { hash_value: "hash" }, (client: any) => client.computeContentHash({ data: "example" })],
    ["CreateContentHash", { id: "id" }, (client: any) => client.createContentHash({ iriId: "iri-1", hashValue: "hash" })],
    ["FindIRIByHash", { results: [{ iri: "iri" }] }, (client: any) => client.findIRIByHash("hash")],
    ["DefineResolver", { id: "id" }, (client: any) => client.defineResolver({ resolverUrl: "https://example.test", managerAddress: "0x1234" })],
    ["RegisterToResolver", { resolver_id: "id" }, (client: any) => client.registerToResolver({ resolverId: "resolver-1", iriId: "iri-1" })],
    ["GetResolversForIRI", { resolvers: [{ id: "id" }] }, (client: any) => client.getResolversForIRI("iri-1")],
    ["ListResolvers", { resolvers: [{ id: "id" }] }, (client: any) => client.listResolvers()],
    ["AttestToIRI", { id: "id" }, (client: any) => client.attestToIRI({ iriId: "iri-1", attestorAddress: "0x1234" })],
    ["GetAttestorsForIRI", { attestors: [{ id: "id" }] }, (client: any) => client.getAttestorsForIRI("iri-1")],
  ])("rejects malformed %s response", async (rpcName, response, invoke) => {
    const client = await dataClientWithResponses({ [rpcName as string]: response });

    await expect((invoke as (client: any) => Promise<unknown>)(client)).rejects.toThrow(
      `Invalid ${rpcName as string} response`,
    );
  });

  it("normalizes and buffers multiple StreamNewIRIs chunks before iteration", async () => {
    const stream = fakeReadableStream();
    const { DataServiceClient } = await import("../services/data-service");
    const client = Object.create(DataServiceClient.prototype) as InstanceType<
      typeof DataServiceClient
    >;
    Object.assign(client, {
      client: { StreamNewIRIs: () => stream },
      defaultMetadata: {},
    });

    const updates = client.streamNewIRIs();
    stream.emit("data", {
      iri: "kokonut:location:adelphi:v1",
      entity_type: "location",
      entity_id: "adelphi",
      version: 1,
      content_hash: "hash-1",
      timestamp: 100,
    });
    stream.emit("data", {
      iri: "kokonut:location:adelphi:v2",
      entity_type: "location",
      entity_id: "adelphi",
      version: 2,
      content_hash: "hash-2",
      timestamp: 200,
    });
    stream.emit("end");
    stream.emit("close");

    const iterator = updates[Symbol.asyncIterator]();
    await expect(iterator.next()).resolves.toEqual({
      value: {
        iri: "kokonut:location:adelphi:v1",
        entityType: "location",
        entityId: "adelphi",
        version: 1,
        contentHash: "hash-1",
        timestamp: 100,
      },
      done: false,
    });
    await expect(iterator.next()).resolves.toMatchObject({
      value: { version: 2, contentHash: "hash-2" },
      done: false,
    });
    await expect(iterator.next()).resolves.toEqual({ value: undefined, done: true });
  });

  it("maps StreamNewIRIs failures, rejects malformed chunks and cancels on early return", async () => {
    const { DataServiceClient } = await import("../services/data-service");
    const makeStreamClient = () => {
      const stream = fakeReadableStream();
      const client = Object.create(DataServiceClient.prototype) as InstanceType<
        typeof DataServiceClient
      >;
      Object.assign(client, {
        client: { StreamNewIRIs: () => stream },
        defaultMetadata: {},
      });
      return { stream, client };
    };

    const failed = makeStreamClient();
    const failedIterator = failed.client.streamNewIRIs()[Symbol.asyncIterator]();
    const pending = failedIterator.next();
    failed.stream.emit("error", {
      code: 14,
      message: "unavailable",
      details: "service unavailable",
    });
    await expect(pending).rejects.toMatchObject({ code: 14, name: "UnavailableError" });
    await expect(failedIterator.next()).rejects.toMatchObject({ code: 14 });

    const malformed = makeStreamClient();
    const malformedIterator = malformed.client.streamNewIRIs()[Symbol.asyncIterator]();
    const malformedPending = malformedIterator.next();
    malformed.stream.emit("data", { iri: "missing-required-fields" });
    await expect(malformedPending).rejects.toThrow(
      "Invalid StreamNewIRIs response: entity_type must be a string",
    );
    expect(malformed.stream.cancel).toHaveBeenCalledOnce();
    expect(malformed.stream.listenerCount("error")).toBe(0);
    expect(malformed.stream.listenerCount("close")).toBe(0);

    const cancelled = makeStreamClient();
    const cancelledIterator = cancelled.client.streamNewIRIs()[Symbol.asyncIterator]();
    await expect(cancelledIterator.return?.()).resolves.toEqual({
      value: undefined,
      done: true,
    });
    expect(cancelled.stream.cancel).toHaveBeenCalledOnce();
    expect(cancelled.stream.listenerCount("error")).toBe(0);
    expect(cancelled.stream.listenerCount("close")).toBe(0);
  });

  it("pauses stream buffering at the high-water mark and resumes as items drain", async () => {
    const stream = fakeReadableStream();
    const { DataServiceClient } = await import("../services/data-service");
    const client = Object.create(DataServiceClient.prototype) as InstanceType<
      typeof DataServiceClient
    >;
    Object.assign(client, {
      client: { StreamNewIRIs: () => stream },
      defaultMetadata: {},
    });

    const updates = client.streamNewIRIs();
    const emitUpdate = (version: number) =>
      stream.emit("data", {
        iri: `kokonut:location:adelphi:v${version}`,
        entity_type: "location",
        entity_id: "adelphi",
        version,
        content_hash: `hash-${version}`,
        timestamp: version,
      });
    for (let version = 1; version <= 32; version += 1) emitUpdate(version);
    expect(stream.pause).toHaveBeenCalledOnce();

    const iterator = updates[Symbol.asyncIterator]();
    for (let version = 1; version <= 16; version += 1) {
      await expect(iterator.next()).resolves.toMatchObject({
        value: { version },
        done: false,
      });
    }
    expect(stream.resume).toHaveBeenCalledOnce();

    for (let version = 33; version <= 40; version += 1) emitUpdate(version);
    stream.emit("end");
    stream.emit("close");
    for (let version = 17; version <= 40; version += 1) {
      await expect(iterator.next()).resolves.toMatchObject({
        value: { version },
        done: false,
      });
    }
    await expect(iterator.next()).resolves.toEqual({ value: undefined, done: true });
  });
});

describe("EcocreditServiceClient", () => {
  it("can be constructed with an address", async () => {
    const { EcocreditServiceClient } = await import(
      "../services/ecocredit-service"
    );
    const client = new EcocreditServiceClient("localhost:50051");
    expect(client).toBeDefined();
    expect(typeof client.close).toBe("function");
    expect(typeof client.classes).toBe("function");
    expect(typeof client.class).toBe("function");
    expect(typeof client.createClass).toBe("function");
    expect(typeof client.batches).toBe("function");
    expect(typeof client.balance).toBe("function");
    expect(typeof client.baskets).toBe("function");
    expect(typeof client.sellOrders).toBe("function");
    expect(typeof client.bridgeOut).toBe("function");
    expect(typeof client.applyToClass).toBe("function");
    expect(typeof client.creditTypes).toBe("function");
    expect(typeof client.streamBalances).toBe("function");
    expect(typeof client.streamBatchUpdates).toBe("function");
    expect(typeof client.streamSellOrders).toBe("function");
    client.close();
  });
});
