import { afterEach, describe, expect, it, vi } from "vitest";

import {
  EcocreditServiceClient,
  type GrpcPageRequest,
} from "../services/ecocredit-service";

type PaginatedList = {
  method: string;
  invoke: (
    client: EcocreditServiceClient,
    pagination?: GrpcPageRequest,
  ) => Promise<unknown>;
  baseRequest: Record<string, string>;
};

const paginatedLists: PaginatedList[] = [
  {
    method: "Classes",
    invoke: (client, page) => client.classes(page),
    baseRequest: {},
  },
  {
    method: "ClassesByAdmin",
    invoke: (client, page) => client.classesByAdmin("admin-1", page),
    baseRequest: { admin: "admin-1" },
  },
  {
    method: "Projects",
    invoke: (client, page) => client.projects(page),
    baseRequest: {},
  },
  {
    method: "ProjectsByClass",
    invoke: (client, page) => client.projectsByClass("class-1", page),
    baseRequest: { class_id: "class-1" },
  },
  {
    method: "Batches",
    invoke: (client, page) => client.batches(page),
    baseRequest: {},
  },
  {
    method: "BatchesByClass",
    invoke: (client, page) => client.batchesByClass("class-1", page),
    baseRequest: { class_id: "class-1" },
  },
  {
    method: "BatchesByProject",
    invoke: (client, page) => client.batchesByProject("location-1", page),
    baseRequest: { location_id: "location-1" },
  },
  {
    method: "Baskets",
    invoke: (client, page) => client.baskets(page),
    baseRequest: {},
  },
  {
    method: "SellOrders",
    invoke: (client, page) =>
      client.sellOrders({
        batchId: "batch-1",
        sellerAddress: "seller-1",
        pagination: page,
      }),
    baseRequest: { batch_id: "batch-1", seller_address: "seller-1" },
  },
];

describe("EcocreditServiceClient pagination", () => {
  afterEach(() => vi.restoreAllMocks());

  it.each(paginatedLists)(
    "$method forwards cursor pagination",
    async ({ method, invoke, baseRequest }) => {
      const client = new EcocreditServiceClient("127.0.0.1:50051");
      const call = vi.spyOn(client as any, "_call").mockResolvedValue({});
      const offset = Uint8Array.from([1, 2, 3]);

      await invoke(client, { limit: 25, offset });

      expect(call).toHaveBeenCalledWith(method, {
        ...baseRequest,
        pagination: { limit: 25, offset },
      });
      client.close();
    },
  );

  it.each(paginatedLists)(
    "$method keeps pagination optional",
    async ({ method, invoke, baseRequest }) => {
      const client = new EcocreditServiceClient("127.0.0.1:50051");
      const call = vi.spyOn(client as any, "_call").mockResolvedValue({});

      await invoke(client);

      expect(call).toHaveBeenCalledWith(method, baseRequest);
      client.close();
    },
  );
});
