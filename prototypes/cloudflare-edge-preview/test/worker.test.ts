import { createExecutionContext, env } from "cloudflare:test";
import { describe, expect, it } from "vitest";
import worker from "../src/index";

describe("synthetic edge preview", () => {
  it("reports that only synthetic content is available and no backend is connected", async () => {
    const response = await worker.fetch(
      new Request("https://preview.example/healthz"),
      env,
      createExecutionContext(),
    );

    expect(response.status).toBe(200);
    expect(response.headers.get("cache-control")).toBe("no-store");
    expect(await response.json()).toEqual({
      status: "ok",
      service: "ki-edge-preview",
      dataMode: "synthetic-only",
      backendConnected: false,
    });
  });

  it("rejects unsupported health methods", async () => {
    const response = await worker.fetch(
      new Request("https://preview.example/healthz", { method: "POST" }),
      env,
      createExecutionContext(),
    );

    expect(response.status).toBe(405);
    expect(response.headers.get("allow")).toBe("GET, HEAD");
  });

  it("keeps API requests disconnected from KI data services", async () => {
    const response = await worker.fetch(
      new Request("https://preview.example/api/farms"),
      env,
      createExecutionContext(),
    );

    expect(response.status).toBe(404);
    expect(response.headers.get("cache-control")).toBe("no-store");
    expect(await response.json()).toEqual({
      error: "not_found",
      backendConnected: false,
    });
  });

  it("serves the synthetic preview page through the static-assets binding", async () => {
    const response = await worker.fetch(
      new Request("https://preview.example/"),
      env,
      createExecutionContext(),
    );

    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toContain("text/html");
    expect(await response.text()).toContain("Synthetic-only preview");
  });
});
