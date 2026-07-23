import { describe, it, expect } from "vitest";

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
