/**
 * Typed wrapper for the gRPC EcocreditService.
 *
 * Uses @grpc/proto-loader for runtime proto loading with generated
 * @bufbuild/protobuf types for compile-time type safety.
 */

import {
  Client,
  Metadata,
  credentials,
  type ChannelCredentials,
  type ServiceError,
} from "@grpc/grpc-js";
import * as protoLoader from "@grpc/proto-loader";
import path from "path";

import { KokonutGrpcError } from "../errors";

/** Options for constructing an EcocreditServiceClient. */
export interface EcocreditServiceClientOptions {
  credentials?: ChannelCredentials;
  metadata?: Metadata;
}

/** Thin typed wrapper around the raw gRPC EcocreditService client. */
export class EcocreditServiceClient {
  private readonly client: Client;
  private readonly defaultMetadata: Metadata;

  constructor(address: string, options: EcocreditServiceClientOptions = {}) {
    const repoRoot = path.resolve(__dirname, "../../../../");
    const protoPath = path.resolve(repoRoot, "proto/ecocredit/v1/service.proto");
    const packageDefinition = protoLoader.loadSync(protoPath, {
      keepCase: true,
      longs: Number,
      enums: String,
      defaults: true,
      oneofs: true,
      includeDirs: [path.resolve(repoRoot, "proto")],
    });
    const grpc = require("@grpc/grpc-js");
    const ServiceDefinition = grpc.loadPackageDefinition(packageDefinition)
      .ecocredit?.v1?.EcocreditService;
    if (!ServiceDefinition) {
      throw new Error("Failed to load EcocreditService proto definition");
    }

    this.client = new ServiceDefinition(
      address,
      options.credentials ?? credentials.createInsecure(),
    ) as Client;
    this.defaultMetadata = options.metadata ?? new Metadata();
  }

  close(): void {
    this.client.close();
  }

  // ── Class Queries ──────────────────────────────────────────────────────

  classes(): Promise<{
    classes: Array<{
      id: string;
      name: string;
      description: string;
      creditType: string;
      adminAddress: string;
      status: string;
    }>;
  }> {
    return this._call("Classes", {});
  }

  class(classId: string): Promise<{
    classInfo: {
      id: string;
      name: string;
      description: string;
      creditType: string;
      adminAddress: string;
      status: string;
    };
  }> {
    return this._call("Class", { class_id: classId });
  }

  classesByAdmin(admin: string): Promise<{
    classes: Array<{
      id: string;
      name: string;
      creditType: string;
      adminAddress: string;
      status: string;
    }>;
  }> {
    return this._call("ClassesByAdmin", { admin });
  }

  classIssuers(classId: string): Promise<{
    issuers: Array<{
      id: string;
      creditClassId: string;
      issuerAddress: string;
      issuerName: string;
    }>;
  }> {
    return this._call("ClassIssuers", { class_id: classId });
  }

  // ── Class Mutations ────────────────────────────────────────────────────

  createClass(req: {
    name: string;
    methodology: string;
    creditType: string;
    description?: string;
    url?: string;
    adminAddress: string;
  }): Promise<{ classId: string }> {
    return this._call("CreateClass", {
      name: req.name,
      methodology: req.methodology,
      credit_type: req.creditType,
      description: req.description ?? "",
      url: req.url ?? "",
      admin_address: req.adminAddress,
    });
  }

  updateClass(req: {
    classId: string;
    name?: string;
    description?: string;
    url?: string;
    methodology?: string;
    status?: string;
  }): Promise<{ classId: string }> {
    return this._call("UpdateClass", {
      class_id: req.classId,
      name: req.name ?? "",
      description: req.description ?? "",
      url: req.url ?? "",
      methodology: req.methodology ?? "",
      status: req.status ?? "",
    });
  }

  // ── Project Queries ────────────────────────────────────────────────────

  projects(): Promise<{
    projects: Array<{
      name: string;
      description: string;
      region: string;
      watershed: string;
    }>;
  }> {
    return this._call("Projects", {});
  }

  project(locationId: string): Promise<{
    project: {
      name: string;
      description: string;
      region: string;
      watershed: string;
    };
  }> {
    return this._call("Project", { location_id: locationId });
  }

  projectsByClass(classId: string): Promise<{
    projects: Array<{
      name: string;
      region: string;
    }>;
  }> {
    return this._call("ProjectsByClass", { class_id: classId });
  }

  // ── Batch Queries ──────────────────────────────────────────────────────

  batches(): Promise<{
    batches: Array<{
      id: string;
      batchCode: string;
      creditClassId: string;
      locationId: string;
      vintageYear: number;
      totalQuantity: number;
      issuedQuantity: number;
      availableQuantity: number;
      unit: string;
      status: string;
    }>;
  }> {
    return this._call("Batches", {});
  }

  batch(batchId: string): Promise<{
    batch: {
      id: string;
      batchCode: string;
      creditClassId: string;
      locationId: string;
      vintageYear: number;
      totalQuantity: number;
      issuedQuantity: number;
      availableQuantity: number;
      unit: string;
      status: string;
    };
  }> {
    return this._call("Batch", { batch_id: batchId });
  }

  batchesByClass(classId: string): Promise<{
    batches: Array<{
      id: string;
      batchCode: string;
      vintageYear: number;
      totalQuantity: number;
      unit: string;
      status: string;
    }>;
  }> {
    return this._call("BatchesByClass", { class_id: classId });
  }

  batchesByProject(locationId: string): Promise<{
    batches: Array<{
      id: string;
      batchCode: string;
      vintageYear: number;
      totalQuantity: number;
      unit: string;
      status: string;
    }>;
  }> {
    return this._call("BatchesByProject", { location_id: locationId });
  }

  // ── Batch Mutations ────────────────────────────────────────────────────

  createBatch(req: {
    creditClassId: string;
    locationId: string;
    vintageYear: number;
    totalQuantity: number;
    unit?: string;
  }): Promise<{ batchId: string; batchCode: string }> {
    return this._call("CreateBatch", {
      credit_class_id: req.creditClassId,
      location_id: req.locationId,
      vintage_year: req.vintageYear,
      total_quantity: req.totalQuantity,
      unit: req.unit ?? "tonneCO2e",
    });
  }

  // ── Balance Queries ────────────────────────────────────────────────────

  balance(batchId: string, accountAddress: string): Promise<{
    balance: {
      creditBatchId: string;
      accountAddress: string;
      tradableAmount: number;
      retiredAmount: number;
      escrowedAmount: number;
    };
  }> {
    return this._call("Balance", {
      batch_id: batchId,
      account_address: accountAddress,
    });
  }

  balances(accountAddress: string): Promise<{
    balances: Array<{
      creditBatchId: string;
      batchCode: string;
      accountAddress: string;
      tradableAmount: number;
      retiredAmount: number;
      escrowedAmount: number;
      unit: string;
    }>;
  }> {
    return this._call("Balances", { account_address: accountAddress });
  }

  balancesByBatch(batchId: string): Promise<{
    balances: Array<{
      creditBatchId: string;
      accountAddress: string;
      tradableAmount: number;
      retiredAmount: number;
      escrowedAmount: number;
    }>;
  }> {
    return this._call("BalancesByBatch", { batch_id: batchId });
  }

  supply(batchId: string): Promise<{
    supply: {
      creditBatchId: string;
      tradableSupply: number;
      retiredSupply: number;
      escrowedSupply: number;
    };
  }> {
    return this._call("Supply", { batch_id: batchId });
  }

  // ── Streaming ──────────────────────────────────────────────────────────

  streamBalances(
    accountAddress: string,
  ): AsyncIterable<{
    batchId: string;
    accountAddress: string;
    tradableAmount: number;
    retiredAmount: number;
    escrowedAmount: number;
    timestamp: number;
  }> {
    const call = (this.client as any).StreamBalances(
      { account_address: accountAddress },
      this.defaultMetadata,
    );
    return this._wrapStream(call);
  }

  streamBatchUpdates(classId?: string): AsyncIterable<{
    batchId: string;
    batchCode: string;
    status: string;
    issuedQuantity: number;
    retiredQuantity: number;
    timestamp: number;
  }> {
    const call = (this.client as any).StreamBatchUpdates(
      { class_id: classId ?? "" },
      this.defaultMetadata,
    );
    return this._wrapStream(call);
  }

  // ── Basket ─────────────────────────────────────────────────────────────

  baskets(): Promise<{
    baskets: Array<{
      id: string;
      name: string;
      description: string;
      basketDenom: string;
      disableAutoRetire: boolean;
      curatorAddress: string;
      exponent: number;
      status: string;
    }>;
  }> {
    return this._call("Baskets", {});
  }

  basket(basketId: string): Promise<{
    basket: {
      id: string;
      name: string;
      basketDenom: string;
      disableAutoRetire: boolean;
      curatorAddress: string;
      exponent: number;
      classes: Array<{ id: string; name: string }>;
      status: string;
    };
  }> {
    return this._call("Basket", { basket_id: basketId });
  }

  createBasket(req: {
    name: string;
    description?: string;
    creditTypeAbbrev: string;
    creditClassIds: string[];
    disableAutoRetire?: boolean;
    curatorAddress: string;
    minStartYear?: number;
  }): Promise<{ basketId: string; basketDenom: string }> {
    return this._call("CreateBasket", {
      name: req.name,
      description: req.description ?? "",
      credit_type_abbrev: req.creditTypeAbbrev,
      credit_class_ids: req.creditClassIds,
      disable_auto_retire: req.disableAutoRetire ?? false,
      curator_address: req.curatorAddress,
      min_start_year: req.minStartYear ?? 0,
    });
  }

  putInBasket(req: {
    basketId: string;
    depositorAddress: string;
    creditBatchId: string;
    quantity: number;
  }): Promise<{ tokenAmount: number }> {
    return this._call("PutInBasket", {
      basket_id: req.basketId,
      depositor_address: req.depositorAddress,
      credit_batch_id: req.creditBatchId,
      quantity: req.quantity,
    });
  }

  takeFromBasket(req: {
    basketId: string;
    holderAddress: string;
    tokenAmount: number;
    retireOnTake?: boolean;
    retirementJurisdiction?: string;
  }): Promise<{ creditAmount: number; retired: boolean }> {
    return this._call("TakeFromBasket", {
      basket_id: req.basketId,
      holder_address: req.holderAddress,
      token_amount: req.tokenAmount,
      retire_on_take: req.retireOnTake ?? false,
      retirement_jurisdiction: req.retirementJurisdiction ?? "",
    });
  }

  // ── Marketplace ────────────────────────────────────────────────────────

  sellOrders(req?: {
    batchId?: string;
    sellerAddress?: string;
  }): Promise<{
    sellOrders: Array<{
      id: string;
      batchCode: string;
      sellerAddress: string;
      quantity: number;
      askPrice: number;
      askDenom: string;
      disableAutoRetire: boolean;
      expiration: string;
      status: string;
    }>;
  }> {
    return this._call("SellOrders", {
      batch_id: req?.batchId ?? "",
      seller_address: req?.sellerAddress ?? "",
    });
  }

  sellOrder(orderId: string): Promise<{
    sellOrder: {
      id: string;
      sellerAddress: string;
      quantity: number;
      askPrice: number;
      askDenom: string;
      status: string;
    };
  }> {
    return this._call("SellOrder", { order_id: orderId });
  }

  createSellOrder(req: {
    creditBatchId: string;
    sellerAddress: string;
    quantity: number;
    askPrice: number;
    askDenom: string;
    disableAutoRetire?: boolean;
    expiration?: string;
    allowPartialFills?: boolean;
  }): Promise<{ orderId: string }> {
    return this._call("CreateSellOrder", {
      credit_batch_id: req.creditBatchId,
      seller_address: req.sellerAddress,
      quantity: req.quantity,
      ask_price: req.askPrice,
      ask_denom: req.askDenom,
      disable_auto_retire: req.disableAutoRetire ?? false,
      expiration: req.expiration ?? "",
      allow_partial_fills: req.allowPartialFills ?? false,
    });
  }

  updateSellOrder(req: {
    orderId: string;
    sellerAddress: string;
    newQuantity?: number;
    newAskPrice?: number;
    newExpiration?: string;
  }): Promise<{ orderId: string }> {
    return this._call("UpdateSellOrder", {
      order_id: req.orderId,
      seller_address: req.sellerAddress,
      new_quantity: req.newQuantity ?? 0,
      new_ask_price: req.newAskPrice ?? 0,
      new_expiration: req.newExpiration ?? "",
    });
  }

  cancelSellOrder(
    orderId: string,
    sellerAddress: string,
  ): Promise<{ orderId: string; status: string }> {
    return this._call("CancelSellOrder", {
      order_id: orderId,
      seller_address: sellerAddress,
    });
  }

  createBuyOrder(req: {
    sellOrderId: string;
    buyerAddress: string;
    quantity: number;
    disableAutoRetire?: boolean;
    retirementJurisdiction?: string;
    retirementReason?: string;
    maxFeeAmount?: number;
  }): Promise<{ orderId: string; totalPrice: number; buyerFee: number }> {
    return this._call("CreateBuyOrder", {
      sell_order_id: req.sellOrderId,
      buyer_address: req.buyerAddress,
      quantity: req.quantity,
      disable_auto_retire: req.disableAutoRetire ?? false,
      retirement_jurisdiction: req.retirementJurisdiction ?? "",
      retirement_reason: req.retirementReason ?? "",
      max_fee_amount: req.maxFeeAmount ?? 0,
    });
  }

  executeBuyOrder(buyOrderId: string): Promise<{
    buyOrderId: string;
    status: string;
  }> {
    return this._call("ExecuteBuyOrder", { buy_order_id: buyOrderId });
  }

  streamSellOrders(batchId?: string): AsyncIterable<{
    orderId: string;
    sellerAddress: string;
    quantity: number;
    askPrice: number;
    status: string;
    timestamp: number;
  }> {
    const call = (this.client as any).StreamSellOrders(
      { batch_id: batchId ?? "" },
      this.defaultMetadata,
    );
    return this._wrapStream(call);
  }

  // ── Allowed Denoms ─────────────────────────────────────────────────────

  allowedDenoms(): Promise<{
    allowedDenoms: Array<{
      id: string;
      denom: string;
      chain: string;
      isActive: boolean;
    }>;
  }> {
    return this._call("AllowedDenoms", {});
  }

  // ── Fee Params ─────────────────────────────────────────────────────────

  getFeeParams(): Promise<{
    feeParams: {
      buyerFee: number;
      sellerFee: number;
    };
  }> {
    return this._call("GetFeeParams", {});
  }

  // ── Bridge ─────────────────────────────────────────────────────────────

  bridgeOut(req: {
    creditBatchId: string;
    senderAddress: string;
    targetChain: string;
    recipientAddress: string;
    quantity: number;
  }): Promise<{ bridgeTxId: string }> {
    return this._call("BridgeOut", {
      credit_batch_id: req.creditBatchId,
      sender_address: req.senderAddress,
      target_chain: req.targetChain,
      recipient_address: req.recipientAddress,
      quantity: req.quantity,
    });
  }

  bridgeIn(req: {
    creditClassId: string;
    sourceChain: string;
    issuerAddress: string;
    recipientAddress: string;
    quantity: number;
    originTxId?: string;
  }): Promise<{ bridgeTxId: string }> {
    return this._call("BridgeIn", {
      credit_class_id: req.creditClassId,
      source_chain: req.sourceChain,
      issuer_address: req.issuerAddress,
      recipient_address: req.recipientAddress,
      quantity: req.quantity,
      origin_tx_id: req.originTxId ?? "",
    });
  }

  bridgeComplete(
    bridgeTxId: string,
    bridgeTxHash?: string,
  ): Promise<{ status: string }> {
    return this._call("BridgeComplete", {
      bridge_tx_id: bridgeTxId,
      bridge_tx_hash: bridgeTxHash ?? "",
    });
  }

  // ── Enrollment ─────────────────────────────────────────────────────────

  applyToClass(req: {
    locationId: string;
    creditClassId: string;
    applicationMetadata?: string;
  }): Promise<{ enrollmentId: string; status: string }> {
    return this._call("ApplyToClass", {
      location_id: req.locationId,
      credit_class_id: req.creditClassId,
      application_metadata: req.applicationMetadata ?? "",
    });
  }

  evaluateApplication(req: {
    enrollmentId: string;
    issuerAddress: string;
    newStatus: string;
    enrollmentMetadata?: string;
  }): Promise<{
    enrollmentId: string;
    oldStatus: string;
    newStatus: string;
  }> {
    return this._call("EvaluateApplication", {
      enrollment_id: req.enrollmentId,
      issuer_address: req.issuerAddress,
      new_status: req.newStatus,
      enrollment_metadata: req.enrollmentMetadata ?? "",
    });
  }

  listEnrollments(req?: {
    locationId?: string;
    classId?: string;
  }): Promise<{
    enrollments: Array<{
      id: string;
      locationId: string;
      creditClassId: string;
      status: string;
    }>;
  }> {
    return this._call("ListEnrollments", {
      location_id: req?.locationId ?? "",
      class_id: req?.classId ?? "",
    });
  }

  // ── Credit Types ───────────────────────────────────────────────────────

  creditTypes(): Promise<{
    creditTypes: Array<{
      abbreviation: string;
      name: string;
      unit: string;
      precision: number;
      description: string;
    }>;
  }> {
    return this._call("CreditTypes", {});
  }

  // ── Internal ───────────────────────────────────────────────────────────

  private _call<T>(method: string, request: any): Promise<T> {
    return new Promise((resolve, reject) => {
      (this.client as any)[method](
        request,
        this.defaultMetadata,
        (err: ServiceError | null, response: T) => {
          if (err) {
            reject(KokonutGrpcError.fromServiceError(err));
          } else {
            resolve(response);
          }
        },
      );
    });
  }

  private _wrapStream<T>(call: any): AsyncIterable<T> {
    return {
      [Symbol.asyncIterator]() {
        return {
          next(): Promise<IteratorResult<T>> {
            return new Promise((resolve, reject) => {
              call.on("data", (data: T) => resolve({ value: data, done: false }));
              call.on("end", () => resolve({ value: undefined as any, done: true }));
              call.on("error", (err: ServiceError) =>
                reject(KokonutGrpcError.fromServiceError(err)),
              );
            });
          },
        };
      },
    };
  }
}
