import { afterEach, describe, expect, it, vi } from "vitest";
import { credentials, type ChannelCredentials } from "@grpc/grpc-js";

import { resolveChannelCredentials } from "../transport";

describe("resolveChannelCredentials", () => {
  afterEach(() => vi.restoreAllMocks());

  it.each([
    "localhost:50051",
    "dns:///localhost:50051",
    "127.0.0.1:50051",
    "ipv4:127.0.0.1:50051",
    "[::1]:50051",
    "ipv6:[::1]:50051",
  ])("uses plaintext credentials for loopback target %s", (address) => {
    const insecure = vi
      .spyOn(credentials, "createInsecure")
      .mockReturnValue({} as ChannelCredentials);
    const secure = vi
      .spyOn(credentials, "createSsl")
      .mockReturnValue({} as ChannelCredentials);

    const selected = resolveChannelCredentials(address);

    expect(selected).toBe(insecure.mock.results[0]?.value);
    expect(insecure).toHaveBeenCalledOnce();
    expect(secure).not.toHaveBeenCalled();
  });

  it.each(["grpc.internal:50051", "api.kokonut.network:443", "10.0.0.8:50051"])(
    "uses system-trusted TLS credentials for remote target %s",
    (address) => {
      const insecure = vi
        .spyOn(credentials, "createInsecure")
        .mockReturnValue({} as ChannelCredentials);
      const secure = vi
        .spyOn(credentials, "createSsl")
        .mockReturnValue({} as ChannelCredentials);

      const selected = resolveChannelCredentials(address);

      expect(selected).toBe(secure.mock.results[0]?.value);
      expect(secure).toHaveBeenCalledOnce();
      expect(insecure).not.toHaveBeenCalled();
    },
  );

  it("preserves caller-supplied credentials", () => {
    const supplied = {} as ChannelCredentials;
    const insecure = vi.spyOn(credentials, "createInsecure");
    const secure = vi.spyOn(credentials, "createSsl");

    expect(resolveChannelCredentials("grpc.internal:50051", supplied)).toBe(supplied);
    expect(insecure).not.toHaveBeenCalled();
    expect(secure).not.toHaveBeenCalled();
  });
});
