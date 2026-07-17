import {
  Client,
  credentials,
  type ChannelCredentials,
} from "@grpc/grpc-js";

export interface KokonutClientOptions {
  credentials?: ChannelCredentials;
}

/** Shared gRPC transport for generated Kokonut service clients. */
export class KokonutGrpcClient {
  public readonly transport: Client;

  constructor(address: string, options: KokonutClientOptions = {}) {
    this.transport = new Client(
      address,
      options.credentials ?? credentials.createInsecure(),
    );
  }

  close(): void {
    this.transport.close();
  }
}
