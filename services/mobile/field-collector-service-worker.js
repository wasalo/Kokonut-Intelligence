"use strict";

const CACHE_PREFIX = "kokonut-field-collector-shell-";
const CACHE_NAME = `${CACHE_PREFIX}v1`;
const REQUEST_TIMEOUT_MS = 5000;
const APP_ASSET_PAIRS = new Map([
  ["/mobile", "/field-collector-vault.js"],
  ["/mobile/", "/mobile/field-collector-vault.js"],
  ["/api/mobile/app", "/api/mobile/field-collector-vault.js"],
  ["/field/field-collector.html", "/field/field-collector-vault.js"],
]);
const SHELL_PATHS = new Set([
  ...APP_ASSET_PAIRS.keys(),
  ...APP_ASSET_PAIRS.values(),
]);
const VAULT_PATHS = new Set(APP_ASSET_PAIRS.values());

self.addEventListener("install", event => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener("activate", event => {
  event.waitUntil(self.clients.claim());
});

function safeShellUrl(value) {
  try {
    const url = new URL(value);
    if (url.origin !== self.location.origin || url.search || url.hash) return null;
    if (!SHELL_PATHS.has(url.pathname)) return null;
    return url;
  } catch (_) {
    return null;
  }
}

function isCacheableResponse(response, expectedTypes) {
  const cacheControl = (response.headers.get("cache-control") || "").toLowerCase();
  return response.ok
    && response.type === "basic"
    && !response.headers.has("set-cookie")
    && !/\b(?:no-store|private)\b/.test(cacheControl)
    && expectedTypes.some(type => (response.headers.get("content-type") || "").toLowerCase().startsWith(type));
}

async function fetchShellResource(url, expectedType) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(url.href, {
      method: "GET",
      credentials: "same-origin",
      cache: "reload",
      redirect: "error",
      signal: controller.signal,
    });
    if (!isCacheableResponse(response, Array.isArray(expectedType) ? expectedType : [expectedType])) {
      throw new Error("Field Collector shell response failed its static-content check");
    }
    return response;
  } finally {
    clearTimeout(timeout);
  }
}

async function cacheShellPair(appUrl, vaultUrl) {
  const appResponse = await fetchShellResource(appUrl, "text/html");
  const vaultResponse = await fetchShellResource(vaultUrl, ["application/javascript", "text/javascript"]);
  const stagingName = `${CACHE_NAME}-staging`;
  await caches.delete(stagingName);
  const staging = await caches.open(stagingName);
  try {
    await staging.put(appUrl.href, appResponse);
    await staging.put(vaultUrl.href, vaultResponse);
    const stagedApp = await staging.match(appUrl.href);
    const stagedVault = await staging.match(vaultUrl.href);
    if (!stagedApp || !stagedVault) throw new Error("Field Collector shell staging was incomplete");

    const current = await caches.open(CACHE_NAME);
    await current.put(appUrl.href, stagedApp);
    await current.put(vaultUrl.href, stagedVault);
  } finally {
    await caches.delete(stagingName);
  }

  const names = await caches.keys();
  await Promise.all(names
    .filter(name => name.startsWith(CACHE_PREFIX) && name !== CACHE_NAME)
    .map(name => caches.delete(name)));
}

self.addEventListener("message", event => {
  if (event.data?.type !== "CACHE_FIELD_COLLECTOR_SHELL") return;
  const appUrl = safeShellUrl(event.data.appUrl);
  const vaultUrl = safeShellUrl(event.data.vaultUrl);
  if (!appUrl || !vaultUrl || APP_ASSET_PAIRS.get(appUrl.pathname) !== vaultUrl.pathname) return;
  const scopePath = new URL(self.registration.scope).pathname;
  if (!appUrl.pathname.startsWith(scopePath) || !vaultUrl.pathname.startsWith(scopePath)) return;
  event.waitUntil(cacheShellPair(appUrl, vaultUrl).catch(() => {}));
});

async function networkFirst(request) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(request, { signal: controller.signal });
    const expectedTypes = APP_ASSET_PAIRS.has(new URL(request.url).pathname)
      ? ["text/html"]
      : ["application/javascript", "text/javascript"];
    if (isCacheableResponse(response, expectedTypes)) {
      try {
        const cache = await caches.open(CACHE_NAME);
        await cache.put(request, response.clone());
      } catch (_) {
        // The network response remains usable if storage is full or unavailable.
      }
    }
    return response;
  } catch (error) {
    const cache = await caches.open(CACHE_NAME);
    const cached = await cache.match(request);
    if (cached) return cached;
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

self.addEventListener("fetch", event => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin || url.search || url.hash) return;
  const scopePath = new URL(self.registration.scope).pathname;
  if (!url.pathname.startsWith(scopePath)) return;

  const isAppNavigation = request.mode === "navigate" && APP_ASSET_PAIRS.has(url.pathname);
  const isVaultScript = request.destination === "script" && VAULT_PATHS.has(url.pathname);
  if (!isAppNavigation && !isVaultScript) return;
  event.respondWith(networkFirst(request));
});
