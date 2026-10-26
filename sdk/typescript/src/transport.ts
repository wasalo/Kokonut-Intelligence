import { isIP } from "net";

import {
  credentials,
  type ChannelCredentials,
} from "@grpc/grpc-js";

function isLoopbackTarget(address: string): boolean {
  let target = address.trim();
  for (const prefix of ["dns:///", "ipv4:", "ipv6:"]) {
    if (target.startsWith(prefix)) {
      target = target.slice(prefix.length);
      break;
    }
  }

  let host: string;
  if (target.startsWith("[")) {
    const end = target.indexOf("]");
    if (end < 0) return false;
    host = target.slice(1, end);
  } else {
    const separator = target.lastIndexOf(":");
    host = separator >= 0 ? target.slice(0, separator) : target;
  }

  const normalizedHost = host.toLowerCase();
  if (normalizedHost === "localhost" || normalizedHost === "::1") return true;
  return isIP(normalizedHost) === 4 && normalizedHost.startsWith("127.");
}

/**
 * Choose secure credentials for remote targets and plaintext only for loopback.
 * A caller-supplied ChannelCredentials object always takes precedence.
 */
export function resolveChannelCredentials(
  address: string,
  supplied?: ChannelCredentials,
): ChannelCredentials {
  if (supplied) return supplied;
  return isLoopbackTarget(address)
    ? credentials.createInsecure()
    : credentials.createSsl();
}
