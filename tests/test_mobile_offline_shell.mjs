import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const workerSource = await readFile(
  new URL("../services/mobile/field-collector-service-worker.js", import.meta.url),
  "utf8",
);

function makeResponse(body, contentType) {
  return {
    ok: true,
    type: "basic",
    body,
    headers: {
      get: name => name.toLowerCase() === "content-type" ? contentType : null,
      has: () => false,
    },
    clone() { return makeResponse(body, contentType); },
  };
}

function loadWorker(fetchImpl) {
  const listeners = new Map();
  const records = new Map();
  const cacheApi = {
    async open(name) {
      if (!records.has(name)) records.set(name, new Map());
      const entries = records.get(name);
      return {
        async put(key, value) { entries.set(typeof key === "string" ? key : key.url, value); },
        async match(key) { return entries.get(typeof key === "string" ? key : key.url) || null; },
      };
    },
    async match(key) {
      for (const entries of records.values()) {
        const value = entries.get(typeof key === "string" ? key : key.url);
        if (value) return value;
      }
      return null;
    },
    async keys() { return [...records.keys()]; },
    async delete(name) { return records.delete(name); },
  };
  const self = {
    location: { origin: "https://kernel.test" },
    registration: { scope: "https://kernel.test/" },
    clients: { async claim() {} },
    addEventListener(type, handler) { listeners.set(type, handler); },
    async skipWaiting() {},
  };
  vm.runInNewContext(workerSource, {
    self,
    caches: cacheApi,
    fetch: fetchImpl,
    URL,
    AbortController,
    setTimeout,
    clearTimeout,
  });
  return { listeners, records, cacheApi };
}

test("offline shell caches only the app pair and serves a cached app navigation offline", async () => {
  const calls = [];
  const worker = loadWorker(async url => {
    calls.push(String(url));
    return String(url).endsWith("field-collector-vault.js")
      ? makeResponse("vault-script", "application/javascript; charset=utf-8")
      : makeResponse("field-collector-html", "text/html; charset=utf-8");
  });

  let cachePromise;
  worker.listeners.get("message")({
    data: {
      type: "CACHE_FIELD_COLLECTOR_SHELL",
      appUrl: "https://kernel.test/mobile",
      vaultUrl: "https://kernel.test/field-collector-vault.js",
    },
    waitUntil(promise) { cachePromise = promise; },
  });
  await cachePromise;

  assert.equal(calls.length, 2);
  const cache = worker.records.get("kokonut-field-collector-shell-v1");
  assert.equal(cache.size, 2);
  assert.equal(cache.get("https://kernel.test/mobile").body, "field-collector-html");
  assert.equal(cache.get("https://kernel.test/field-collector-vault.js").body, "vault-script");

  let apiWasIntercepted = false;
  worker.listeners.get("fetch")({
    request: { method: "GET", url: "https://kernel.test/api/mobile/forms", mode: "cors", destination: "" },
    respondWith() { apiWasIntercepted = true; },
  });
  assert.equal(apiWasIntercepted, false, "form and API responses must stay network-only");

  worker.listeners.get("fetch")({
    request: { method: "POST", url: "https://kernel.test/api/mobile/sync", mode: "cors", destination: "" },
    respondWith() { apiWasIntercepted = true; },
  });
  assert.equal(apiWasIntercepted, false, "sync writes must stay network-only");

  const offlineWorker = loadWorker(async () => { throw new Error("offline"); });
  offlineWorker.records.set("kokonut-field-collector-shell-v1", cache);
  let navigation;
  offlineWorker.listeners.get("fetch")({
    request: { method: "GET", url: "https://kernel.test/mobile", mode: "navigate", destination: "document" },
    respondWith(promise) { navigation = promise; },
  });
  assert.equal((await navigation).body, "field-collector-html");
});

test("shell cache messages reject unpaired or cross-origin resources", async () => {
  let requests = 0;
  const worker = loadWorker(async () => {
    requests += 1;
    return makeResponse("unexpected", "text/html");
  });
  let pending;
  worker.listeners.get("message")({
    data: {
      type: "CACHE_FIELD_COLLECTOR_SHELL",
      appUrl: "https://kernel.test/mobile",
      vaultUrl: "https://attacker.test/field-collector-vault.js",
    },
    waitUntil(promise) { pending = promise; },
  });
  assert.equal(pending, undefined);
  assert.equal(requests, 0);
  assert.equal(worker.records.size, 0);
});
