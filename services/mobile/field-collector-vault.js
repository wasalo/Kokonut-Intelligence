(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    root.FieldCollectorVault = api;
  }
})(globalThis, function () {
  "use strict";

  const encoder = new TextEncoder();
  const decoder = new TextDecoder();
  const DEFAULT_ITERATIONS = 310000;
  const DATABASE_NAME = "kokonut-field-vault";
  const DATABASE_VERSION = 1;
  const OBJECT_STORE = "encrypted_state";
  const RECORD_KEY = "state";
  const LEGACY_STORAGE_KEYS = {
    device: "kokonut_field_device",
    queue: "kokonut_field_queue",
    forms: "kokonut_field_forms",
    settings: "kokonut_field_settings",
  };

  function defaultVaultState() {
    return {
      device: null,
      queue: [],
      forms: [],
      settings: { apiBase: "", deviceName: "" },
    };
  }

  function normalizeState(value) {
    const source = value && typeof value === "object" ? value : {};
    const settings = source.settings && typeof source.settings === "object" ? source.settings : {};
    return {
      device: source.device && typeof source.device === "object" ? source.device : null,
      queue: Array.isArray(source.queue) ? source.queue : [],
      forms: Array.isArray(source.forms) ? source.forms : [],
      settings: {
        apiBase: typeof settings.apiBase === "string" ? settings.apiBase : "",
        deviceName: typeof settings.deviceName === "string" ? settings.deviceName : "",
        ...(typeof settings.lastSyncAt === "string" ? { lastSyncAt: settings.lastSyncAt } : {}),
      },
    };
  }

  function clone(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function toBase64(bytes) {
    let binary = "";
    for (const byte of bytes) binary += String.fromCharCode(byte);
    return btoa(binary);
  }

  function fromBase64(value) {
    const binary = atob(value);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
    return bytes;
  }

  async function deriveKey(cryptoApi, passphrase, salt, iterations) {
    const material = await cryptoApi.subtle.importKey(
      "raw",
      encoder.encode(passphrase),
      "PBKDF2",
      false,
      ["deriveKey"],
    );
    return cryptoApi.subtle.deriveKey(
      { name: "PBKDF2", salt, iterations, hash: "SHA-256" },
      material,
      { name: "AES-GCM", length: 256 },
      false,
      ["encrypt", "decrypt"],
    );
  }

  async function encryptState(cryptoApi, key, salt, state) {
    const iv = cryptoApi.getRandomValues(new Uint8Array(12));
    const ciphertext = await cryptoApi.subtle.encrypt(
      { name: "AES-GCM", iv },
      key,
      encoder.encode(JSON.stringify(normalizeState(state))),
    );
    return {
      version: 1,
      salt: toBase64(salt),
      iv: toBase64(iv),
      ciphertext: toBase64(new Uint8Array(ciphertext)),
    };
  }

  async function decryptState(cryptoApi, key, envelope) {
    if (!envelope || envelope.version !== 1) throw new Error("Unsupported encrypted vault format");
    const plaintext = await cryptoApi.subtle.decrypt(
      { name: "AES-GCM", iv: fromBase64(envelope.iv) },
      key,
      fromBase64(envelope.ciphertext),
    );
    return normalizeState(JSON.parse(decoder.decode(plaintext)));
  }

  function readLegacyState(storage) {
    const state = defaultVaultState();
    let hasData = false;
    for (const [property, key] of Object.entries(LEGACY_STORAGE_KEYS)) {
      const raw = storage?.getItem(key);
      if (raw === null || raw === undefined) continue;
      hasData = true;
      let parsed;
      try {
        parsed = JSON.parse(raw);
      } catch (error) {
        throw new Error(`Legacy ${property} data is unreadable; original data was kept`);
      }
      if (property === "settings") {
        state.settings = parsed && typeof parsed === "object" ? parsed : state.settings;
      } else {
        state[property] = parsed;
      }
    }
    return { state: normalizeState(state), hasData };
  }

  function clearLegacyState(storage) {
    if (!storage) return;
    for (const key of Object.values(LEGACY_STORAGE_KEYS)) storage.removeItem(key);
  }

  function hasLegacyData(storage) {
    if (!storage) return false;
    try {
      return Object.values(LEGACY_STORAGE_KEYS).some(key => storage.getItem(key) !== null);
    } catch (_) {
      return false;
    }
  }

  class EncryptedVault {
    constructor(adapter, cryptoApi = globalThis.crypto, options = {}) {
      if (!adapter || typeof adapter.get !== "function" || typeof adapter.put !== "function") {
        throw new TypeError("An encrypted-vault persistence adapter is required");
      }
      this.adapter = adapter;
      this.crypto = cryptoApi;
      this.iterations = options.iterations ?? DEFAULT_ITERATIONS;
      this.key = null;
      this.salt = null;
      this.state = null;
      this.legacyDataPreserved = false;
    }

    isUnlocked() {
      return this.key !== null && this.state !== null;
    }

    getState() {
      if (!this.isUnlocked()) throw new Error("Offline vault is locked");
      return clone(this.state);
    }

    lock() {
      this.key = null;
      this.salt = null;
      this.state = null;
    }

    async unlock(passphrase, legacyStorage = null) {
      if (!this.crypto?.subtle || typeof this.crypto.getRandomValues !== "function") {
        throw new Error("Encrypted offline storage requires Web Crypto in a secure browser context");
      }
      if (typeof passphrase !== "string" || passphrase.length < 12) {
        throw new Error("Use a passphrase with at least 12 characters");
      }
      const existing = await this.adapter.get();
      if (existing) {
        const salt = fromBase64(existing.salt);
        const key = await deriveKey(this.crypto, passphrase, salt, this.iterations);
        let state;
        try {
          state = await decryptState(this.crypto, key, existing);
        } catch (error) {
          throw new Error("Incorrect passphrase or damaged offline vault");
        }
        this.legacyDataPreserved = hasLegacyData(legacyStorage);
        this.key = key;
        this.salt = salt;
        this.state = state;
        return this.getState();
      }

      const legacy = readLegacyState(legacyStorage);
      const salt = this.crypto.getRandomValues(new Uint8Array(16));
      const key = await deriveKey(this.crypto, passphrase, salt, this.iterations);
      const envelope = await encryptState(this.crypto, key, salt, legacy.state);
      await this.adapter.put(envelope);
      const persisted = await this.adapter.get();
      const verified = await decryptState(this.crypto, key, persisted);
      if (JSON.stringify(verified) !== JSON.stringify(legacy.state)) {
        throw new Error("Encrypted offline-vault verification failed; original data was kept");
      }
      if (legacy.hasData) clearLegacyState(legacyStorage);
      this.legacyDataPreserved = false;
      this.key = key;
      this.salt = salt;
      this.state = verified;
      return this.getState();
    }

    async saveState(state) {
      if (!this.isUnlocked()) throw new Error("Offline vault is locked");
      const next = normalizeState(state);
      const envelope = await encryptState(this.crypto, this.key, this.salt, next);
      await this.adapter.put(envelope);
      const persisted = await this.adapter.get();
      const verified = await decryptState(this.crypto, this.key, persisted);
      if (JSON.stringify(verified) !== JSON.stringify(next)) {
        throw new Error("Encrypted offline-vault verification failed");
      }
      this.state = verified;
      return this.getState();
    }
  }

  function createStateWriter(vault) {
    if (!vault || typeof vault.getState !== "function" || typeof vault.saveState !== "function") {
      throw new TypeError("An unlocked encrypted vault is required");
    }
    let pending = Promise.resolve();
    const write = update => {
      const operation = pending.then(async () => {
        const current = vault.getState();
        const next = typeof update === "function" ? update(current) : update;
        return vault.saveState(next);
      });
      pending = operation.catch(() => {});
      return operation;
    };
    write.flush = () => pending;
    return write;
  }

  function createIndexedDbAdapter(indexedDb = globalThis.indexedDB) {
    if (!indexedDb) throw new Error("IndexedDB is unavailable in this browser");
    let databasePromise;
    const open = () => {
      if (!databasePromise) {
        databasePromise = new Promise((resolve, reject) => {
          const request = indexedDb.open(DATABASE_NAME, DATABASE_VERSION);
          request.onupgradeneeded = () => {
            const database = request.result;
            if (!database.objectStoreNames.contains(OBJECT_STORE)) database.createObjectStore(OBJECT_STORE);
          };
          request.onsuccess = () => {
            request.result.onversionchange = () => request.result.close();
            resolve(request.result);
          };
          request.onerror = () => reject(request.error || new Error("Could not open encrypted offline storage"));
          request.onblocked = () => reject(new Error("Encrypted offline storage is blocked by another tab"));
        });
      }
      return databasePromise;
    };
    const transactionDone = transaction => new Promise((resolve, reject) => {
      transaction.oncomplete = () => resolve();
      transaction.onerror = () => reject(transaction.error || new Error("IndexedDB transaction failed"));
      transaction.onabort = () => reject(transaction.error || new Error("IndexedDB transaction aborted"));
    });
    return {
      async get() {
   const database = await open();
   const transaction = database.transaction(OBJECT_STORE, "readonly");
   const completion = transactionDone(transaction);
   const request = transaction.objectStore(OBJECT_STORE).get(RECORD_KEY);
   const result = await new Promise((resolve, reject) => {
     request.onsuccess = () => resolve(request.result ?? null);
     request.onerror = () => reject(request.error || new Error("Could not read encrypted offline storage"));
   });
   await completion;
   return result;
 },
 async put(value) {
   const database = await open();
   const transaction = database.transaction(OBJECT_STORE, "readwrite");
   const completion = transactionDone(transaction);
   transaction.objectStore(OBJECT_STORE).put(value, RECORD_KEY);
   await completion;
 },
    };
  }

  return {
    EncryptedVault,
    createIndexedDbAdapter,
    createStateWriter,
    defaultVaultState,
    LEGACY_STORAGE_KEYS,
  };
});
