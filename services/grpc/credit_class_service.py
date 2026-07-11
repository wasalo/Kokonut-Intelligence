"""Ecocredit gRPC service implementation."""

from __future__ import annotations

import json
import time
from typing import Any

from services.common.logging import get_logger

logger = get_logger("grpc.ecocredit_service")


class EcocreditServiceServicer:
    """Ecocredit service implementing gRPC RPCs."""

    def __init__(self, db_factory):
        self._db_factory = db_factory

    def _get_conn(self):
        return self._db_factory()

    # --- Class queries ---

    def Classes(self, request, context):
        from services.grpc import ecocredit_pb2
        conn = self._get_conn()
        try:
            from services.credit_class.class_manager import list_classes
            classes = list_classes(conn)
            return ecocredit_pb2.ClassesResponse(
                classes=[ecocredit_pb2.ClassInfo(
                    id=c["id"], name=c["name"], description=c.get("description", ""),
                    credit_type=c["credit_type"], admin_address=c.get("admin_address", ""),
                    status=c["status"],
                ) for c in classes]
            )
        finally:
            conn.close()

    def Class(self, request, context):
        from services.grpc import ecocredit_pb2
        conn = self._get_conn()
        try:
            from services.credit_class.class_manager import get_class_full
            cls = get_class_full(conn, request.class_id)
            if not cls:
                context.abort(grpc.StatusCode.NOT_FOUND, f"Class not found: {request.class_id}")
            return ecocredit_pb2.ClassResponse(
                class_info=ecocredit_pb2.ClassInfo(
                    id=cls["id"], name=cls["name"], description=cls.get("description", ""),
                    credit_type=cls["credit_type"], admin_address=cls.get("admin_address", ""),
                    status=cls["status"],
                )
            )
        finally:
            conn.close()

    def ClassesByAdmin(self, request, context):
        from services.grpc import ecocredit_pb2
        conn = self._get_conn()
        try:
            from services.credit_class.class_manager import list_classes
            classes = list_classes(conn)
            filtered = [c for c in classes if c.get("admin_address") == request.admin]
            return ecocredit_pb2.ClassesByAdminResponse(
                classes=[ecocredit_pb2.ClassInfo(
                    id=c["id"], name=c["name"], credit_type=c["credit_type"],
                    admin_address=c.get("admin_address", ""), status=c["status"],
                ) for c in filtered]
            )
        finally:
            conn.close()

    def ClassIssuers(self, request, context):
        from services.grpc import ecocredit_pb2
        conn = self._get_conn()
        try:
            from services.credit_class.entities import list_issuers
            issuers = list_issuers(conn, request.class_id)
            return ecocredit_pb2.ClassIssuersResponse(
                issuers=[ecocredit_pb2.ClassIssuer(
                    id=i["id"], credit_class_id=str(i["credit_class_id"]),
                    issuer_address=i["issuer_address"], issuer_name=i.get("issuer_name", ""),
                ) for i in issuers]
            )
        finally:
            conn.close()

    # --- Class mutations ---

    def CreateClass(self, request, context):
        from services.grpc import ecocredit_pb2
        conn = self._get_conn()
        try:
            from services.credit_class.class_manager import create_class
            result = create_class(
                conn, name=request.name, methodology=request.methodology,
                credit_type=request.credit_type, description=request.description,
                url=request.url, admin_address=request.admin_address,
            )
            return ecocredit_pb2.CreateClassResponse(class_id=result["id"])
        finally:
            conn.close()

    def UpdateClass(self, request, context):
        from services.grpc import ecocredit_pb2
        conn = self._get_conn()
        try:
            from services.credit_class.class_manager import update_class
            kwargs = {}
            if request.name:
                kwargs["name"] = request.name
            if request.description:
                kwargs["description"] = request.description
            if request.url:
                kwargs["url"] = request.url
            if request.methodology:
                kwargs["methodology"] = request.methodology
            if request.status:
                kwargs["status"] = request.status
            update_class(conn, request.class_id, **kwargs)
            return ecocredit_pb2.UpdateClassResponse(class_id=request.class_id)
        finally:
            conn.close()

    # --- Project queries ---

    def Projects(self, request, context):
        from services.grpc import ecocredit_pb2
        from services.metadata_api.project_info import get_project_info
        conn = self._get_conn()
        try:
            results = conn.execute(
                conn.text("SELECT id FROM location WHERE status = 'active' LIMIT 100")
            ).mappings().all()
            projects = []
            for r in results:
                info = get_project_info(conn, str(r["id"]))
                if info:
                    projects.append(ecocredit_pb2.ProjectInfo(
                        name=info["name"], description=info.get("description", ""),
                        region=info.get("region", ""),
                    ))
            return ecocredit_pb2.ProjectsResponse(projects=projects)
        finally:
            conn.close()

    def Project(self, request, context):
        from services.grpc import ecocredit_pb2
        from services.metadata_api.project_info import get_project_info
        conn = self._get_conn()
        try:
            info = get_project_info(conn, request.location_id)
            if not info:
                context.abort(grpc.StatusCode.NOT_FOUND, f"Project not found: {request.location_id}")
            return ecocredit_pb2.ProjectResponse(
                project=ecocredit_pb2.ProjectInfo(
                    name=info["name"], description=info.get("description", ""),
                    region=info.get("region", ""), watershed=info.get("watershed", ""),
                )
            )
        finally:
            conn.close()

    def ProjectsByClass(self, request, context):
        from services.grpc import ecocredit_pb2
        conn = self._get_conn()
        try:
            from services.credit_class.batch_manager import list_batches
            batches = list_batches(conn, credit_class_id=request.class_id)
            location_ids = list(set(b["location_id"] for b in batches if b.get("location_id")))
            projects = []
            for lid in location_ids[:100]:
                from services.metadata_api.project_info import get_project_info
                info = get_project_info(conn, lid)
                if info:
                    projects.append(ecocredit_pb2.ProjectInfo(
                        name=info["name"], region=info.get("region", ""),
                    ))
            return ecocredit_pb2.ProjectsByClassResponse(projects=projects)
        finally:
            conn.close()

    # --- Batch queries ---

    def Batches(self, request, context):
        from services.grpc import ecocredit_pb2
        conn = self._get_conn()
        try:
            from services.credit_class.batch_manager import list_batches
            batches = list_batches(conn)
            return ecocredit_pb2.BatchesResponse(
                batches=[ecocredit_pb2.BatchInfo(
                    id=b["id"], batch_code=b["batch_code"],
                    credit_class_id=str(b["credit_class_id"]),
                    location_id=str(b["location_id"]),
                    vintage_year=b["vintage_year"],
                    total_quantity=float(b["total_quantity"]),
                    issued_quantity=float(b["issued_quantity"]),
                    available_quantity=float(b["available_quantity"]),
                    unit=b["unit"], status=b["status"],
                ) for b in batches]
            )
        finally:
            conn.close()

    def Batch(self, request, context):
        from services.grpc import ecocredit_pb2
        conn = self._get_conn()
        try:
            from services.credit_class.batch_manager import get_batch
            batch = get_batch(conn, request.batch_id)
            if not batch:
                context.abort(grpc.StatusCode.NOT_FOUND, f"Batch not found: {request.batch_id}")
            return ecocredit_pb2.BatchResponse(
                batch=ecocredit_pb2.BatchInfo(
                    id=batch["id"], batch_code=batch["batch_code"],
                    credit_class_id=str(batch["credit_class_id"]),
                    location_id=str(batch["location_id"]),
                    vintage_year=batch["vintage_year"],
                    total_quantity=float(batch["total_quantity"]),
                    issued_quantity=float(batch["issued_quantity"]),
                    available_quantity=float(batch["available_quantity"]),
                    unit=batch["unit"], status=batch["status"],
                )
            )
        finally:
            conn.close()

    def BatchesByClass(self, request, context):
        from services.grpc import ecocredit_pb2
        conn = self._get_conn()
        try:
            from services.credit_class.batch_manager import list_batches
            batches = list_batches(conn, credit_class_id=request.class_id)
            return ecocredit_pb2.BatchesByClassResponse(
                batches=[ecocredit_pb2.BatchInfo(
                    id=b["id"], batch_code=b["batch_code"],
                    vintage_year=b["vintage_year"],
                    total_quantity=float(b["total_quantity"]),
                    unit=b["unit"], status=b["status"],
                ) for b in batches]
            )
        finally:
            conn.close()

    def BatchesByProject(self, request, context):
        from services.grpc import ecocredit_pb2
        conn = self._get_conn()
        try:
            from services.credit_class.batch_manager import list_batches
            batches = list_batches(conn, location_id=request.location_id)
            return ecocredit_pb2.BatchesByProjectResponse(
                batches=[ecocredit_pb2.BatchInfo(
                    id=b["id"], batch_code=b["batch_code"],
                    vintage_year=b["vintage_year"],
                    total_quantity=float(b["total_quantity"]),
                    unit=b["unit"], status=b["status"],
                ) for b in batches]
            )
        finally:
            conn.close()

    # --- Batch mutations ---

    def CreateBatch(self, request, context):
        from services.grpc import ecocredit_pb2
        conn = self._get_conn()
        try:
            from services.credit_class.batch_manager import create_batch
            result = create_batch(
                conn, credit_class_id=request.credit_class_id,
                location_id=request.location_id,
                vintage_year=request.vintage_year,
                total_quantity=request.total_quantity,
                unit=request.unit or "tonneCO2e",
            )
            return ecocredit_pb2.CreateBatchResponse(
                batch_id=result["id"], batch_code=result["batch_code"],
            )
        finally:
            conn.close()

    # --- Balance queries ---

    def Balance(self, request, context):
        from services.grpc import ecocredit_pb2
        conn = self._get_conn()
        try:
            from services.credit_class.balance import get_balance
            bal = get_balance(conn, request.batch_id, request.account_address)
            return ecocredit_pb2.BalanceResponse(
                balance=ecocredit_pb2.Balance(
                    credit_batch_id=bal["credit_batch_id"],
                    account_address=bal["account_address"],
                    tradable_amount=float(bal["tradable_amount"]),
                    retired_amount=float(bal["retired_amount"]),
                    escrowed_amount=float(bal["escrowed_amount"]),
                )
            )
        finally:
            conn.close()

    def Balances(self, request, context):
        from services.grpc import ecocredit_pb2
        conn = self._get_conn()
        try:
            from services.credit_class.balance import get_balances_for_account
            balances = get_balances_for_account(conn, request.account_address)
            return ecocredit_pb2.BalancesResponse(
                balances=[ecocredit_pb2.BalanceInfo(
                    credit_batch_id=b["credit_batch_id"],
                    batch_code=b.get("batch_code", ""),
                    account_address=b["account_address"],
                    tradable_amount=float(b["tradable_amount"]),
                    retired_amount=float(b["retired_amount"]),
                    escrowed_amount=float(b["escrowed_amount"]),
                    unit=b.get("unit", ""),
                ) for b in balances]
            )
        finally:
            conn.close()

    def BalancesByBatch(self, request, context):
        from services.grpc import ecocredit_pb2
        conn = self._get_conn()
        try:
            from services.credit_class.balance import get_balances_for_batch
            balances = get_balances_for_batch(conn, request.batch_id)
            return ecocredit_pb2.BalancesByBatchResponse(
                balances=[ecocredit_pb2.BalanceInfo(
                    credit_batch_id=b["credit_batch_id"],
                    account_address=b["account_address"],
                    tradable_amount=float(b["tradable_amount"]),
                    retired_amount=float(b["retired_amount"]),
                    escrowed_amount=float(b["escrowed_amount"]),
                ) for b in balances]
            )
        finally:
            conn.close()

    def Supply(self, request, context):
        from services.grpc import ecocredit_pb2
        conn = self._get_conn()
        try:
            from services.credit_class.balance import get_supply
            supply = get_supply(conn, request.batch_id)
            return ecocredit_pb2.SupplyResponse(
                supply=ecocredit_pb2.BatchSupply(
                    credit_batch_id=supply["credit_batch_id"],
                    tradable_supply=supply["tradable_supply"],
                    retired_supply=supply["retired_supply"],
                    escrowed_supply=supply["escrowed_supply"],
                )
            )
        finally:
            conn.close()

    # --- Streaming ---

    def StreamBalances(self, request, context):
        from services.grpc import ecocredit_pb2
        conn = self._get_conn()
        try:
            from services.credit_class.balance import get_balances_for_account
            while context.is_active():
                balances = get_balances_for_account(conn, request.account_address)
                for b in balances:
                    yield ecocredit_pb2.BalanceUpdate(
                        batch_id=b["credit_batch_id"],
                        account_address=b["account_address"],
                        tradable_amount=float(b["tradable_amount"]),
                        retired_amount=float(b["retired_amount"]),
                        escrowed_amount=float(b["escrowed_amount"]),
                        timestamp=int(time.time()),
                    )
                time.sleep(5)
        finally:
            conn.close()

    def StreamBatchUpdates(self, request, context):
        from services.grpc import ecocredit_pb2
        conn = self._get_conn()
        try:
            last_check = int(time.time())
            while context.is_active():
                time.sleep(5)
                now = int(time.time())
                batches = conn.execute(
                    conn.text(
                        "SELECT id, batch_code, status, issued_quantity, retired_quantity, updated_at "
                        "FROM credit_batch WHERE updated_at > :last_check ORDER BY updated_at"
                    ),
                    {"last_check": last_check},
                ).mappings().all()
                for b in batches:
                    yield ecocredit_pb2.BatchUpdate(
                        batch_id=str(b["id"]),
                        batch_code=b["batch_code"],
                        status=b["status"],
                        issued_quantity=float(b["issued_quantity"]),
                        retired_quantity=float(b["retired_quantity"]),
                        timestamp=int(b["updated_at"].timestamp()) if b["updated_at"] else now,
                    )
                last_check = now
        finally:
            conn.close()

    # --- Basket ---

    def Baskets(self, request, context):
        from services.grpc import ecocredit_pb2
        conn = self._get_conn()
        try:
            from services.credit_class.basket import list_baskets
            baskets = list_baskets(conn)
            return ecocredit_pb2.BasketsResponse(
                baskets=[ecocredit_pb2.BasketInfo(
                    id=b["id"], name=b["name"], description=b.get("description", ""),
                    basket_denom=b.get("basket_denom", ""),
                    disable_auto_retire=b.get("disable_auto_retire", False),
                    curator_address=b.get("curator_address", ""),
                    exponent=b.get("exponent", 6),
                    status=b["status"],
                ) for b in baskets]
            )
        finally:
            conn.close()

    def Basket(self, request, context):
        from services.grpc import ecocredit_pb2
        conn = self._get_conn()
        try:
            from services.credit_class.basket import get_basket_info
            basket = get_basket_info(conn, request.basket_id)
            if not basket:
                context.abort(grpc.StatusCode.NOT_FOUND, f"Basket not found: {request.basket_id}")
            classes = [ecocredit_pb2.ClassInfo(id=c["id"], name=c["name"]) for c in basket.get("classes", [])]
            return ecocredit_pb2.BasketResponse(
                basket=ecocredit_pb2.BasketInfo(
                    id=basket["id"], name=basket["name"],
                    basket_denom=basket.get("basket_denom", ""),
                    disable_auto_retire=basket.get("disable_auto_retire", False),
                    curator_address=basket.get("curator_address", ""),
                    exponent=basket.get("exponent", 6),
                    classes=classes, status=basket["status"],
                )
            )
        finally:
            conn.close()

    def CreateBasket(self, request, context):
        from services.grpc import ecocredit_pb2
        conn = self._get_conn()
        try:
            from services.credit_class.basket import create_basket
            result = create_basket(
                conn, name=request.name, description=request.description,
                credit_type_abbrev=request.credit_type_abbrev,
                credit_class_ids=list(request.credit_class_ids),
                disable_auto_retire=request.disable_auto_retire,
                curator_address=request.curator_address,
                min_start_year=request.min_start_year or None,
            )
            return ecocredit_pb2.CreateBasketResponse(
                basket_id=result["id"], basket_denom=result.get("basket_denom", ""),
            )
        finally:
            conn.close()

    def PutInBasket(self, request, context):
        from services.grpc import ecocredit_pb2
        conn = self._get_conn()
        try:
            from services.credit_class.basket import deposit_credits
            result = deposit_credits(
                conn, basket_id=request.basket_id,
                credit_batch_id=request.credit_batch_id,
                depositor_address=request.depositor_address,
                quantity=request.quantity,
            )
            return ecocredit_pb2.PutInBasketResponse(token_amount=result["token_amount"])
        finally:
            conn.close()

    def TakeFromBasket(self, request, context):
        from services.grpc import ecocredit_pb2
        conn = self._get_conn()
        try:
            from services.credit_class.basket import withdraw_from_basket
            result = withdraw_from_basket(
                conn, basket_id=request.basket_id,
                holder_address=request.holder_address,
                quantity=request.token_amount,
                retire_on_take=request.retire_on_take,
                retirement_jurisdiction=request.retirement_jurisdiction or None,
            )
            return ecocredit_pb2.TakeFromBasketResponse(
                credit_amount=result["credit_amount"],
                retired=result["retire_on_take"],
            )
        finally:
            conn.close()

    # --- Marketplace ---

    def SellOrders(self, request, context):
        from services.grpc import ecocredit_pb2
        conn = self._get_conn()
        try:
            from services.credit_class.marketplace import list_sell_orders
            orders = list_sell_orders(conn, credit_batch_id=request.batch_id or None,
                                      seller_address=request.seller_address or None)
            return ecocredit_pb2.SellOrdersResponse(
                sell_orders=[ecocredit_pb2.SellOrderInfo(
                    id=o["id"], batch_code=o.get("batch_code", ""),
                    seller_address=o["seller_address"],
                    quantity=float(o["quantity"]),
                    ask_price=float(o["ask_price"]),
                    ask_denom=o["ask_denom"],
                    disable_auto_retire=o.get("disable_auto_retire", False),
                    expiration=str(o.get("expiration", "")),
                    status=o["status"],
                ) for o in orders]
            )
        finally:
            conn.close()

    def SellOrder(self, request, context):
        from services.grpc import ecocredit_pb2
        conn = self._get_conn()
        try:
            from services.credit_class.marketplace import get_sell_order
            order = get_sell_order(conn, request.order_id)
            if not order:
                context.abort(grpc.StatusCode.NOT_FOUND, f"Order not found: {request.order_id}")
            return ecocredit_pb2.SellOrderResponse(
                sell_order=ecocredit_pb2.SellOrderInfo(
                    id=order["id"], seller_address=order["seller_address"],
                    quantity=float(order["quantity"]),
                    ask_price=float(order["ask_price"]),
                    ask_denom=order["ask_denom"],
                    status=order["status"],
                )
            )
        finally:
            conn.close()

    def CreateSellOrder(self, request, context):
        from services.grpc import ecocredit_pb2
        conn = self._get_conn()
        try:
            from services.credit_class.marketplace import create_sell_order
            result = create_sell_order(
                conn, credit_batch_id=request.credit_batch_id,
                seller_address=request.seller_address,
                quantity=request.quantity, ask_price=request.ask_price,
                ask_denom=request.ask_denom,
                disable_auto_retire=request.disable_auto_retire,
                expiration=request.expiration or None,
                allow_partial_fills=request.allow_partial_fills,
            )
            return ecocredit_pb2.CreateSellOrderResponse(order_id=result["id"])
        finally:
            conn.close()

    def UpdateSellOrder(self, request, context):
        from services.grpc import ecocredit_pb2
        conn = self._get_conn()
        try:
            from services.credit_class.marketplace import update_sell_order
            kwargs = {"new_quantity": request.new_quantity or None,
                      "new_ask_price": request.new_ask_price or None,
                      "new_expiration": request.new_expiration or None}
            kwargs = {k: v for k, v in kwargs.items() if v is not None}
            result = update_sell_order(conn, request.order_id, request.seller_address, **kwargs)
            return ecocredit_pb2.UpdateSellOrderResponse(order_id=result["id"])
        finally:
            conn.close()

    def CancelSellOrder(self, request, context):
        from services.grpc import ecocredit_pb2
        conn = self._get_conn()
        try:
            from services.credit_class.marketplace import cancel_sell_order
            result = cancel_sell_order(conn, request.order_id, request.seller_address)
            return ecocredit_pb2.CancelSellOrderResponse(
                order_id=result["id"], status=result["status"],
            )
        finally:
            conn.close()

    def CreateBuyOrder(self, request, context):
        from services.grpc import ecocredit_pb2
        conn = self._get_conn()
        try:
            from services.credit_class.marketplace import create_buy_order
            result = create_buy_order(
                conn, sell_order_id=request.sell_order_id,
                buyer_address=request.buyer_address,
                quantity=request.quantity,
                disable_auto_retire=request.disable_auto_retire,
                retirement_jurisdiction=request.retirement_jurisdiction or None,
                retirement_reason=request.retirement_reason or None,
                max_fee_amount=request.max_fee_amount or None,
            )
            return ecocredit_pb2.CreateBuyOrderResponse(
                order_id=result["id"],
                total_price=result["total_price"],
                buyer_fee=result.get("buyer_fee", 0),
            )
        finally:
            conn.close()

    def ExecuteBuyOrder(self, request, context):
        from services.grpc import ecocredit_pb2
        conn = self._get_conn()
        try:
            from services.credit_class.marketplace import execute_buy_order
            result = execute_buy_order(conn, request.buy_order_id)
            return ecocredit_pb2.ExecuteBuyOrderResponse(
                buy_order_id=result["buy_order_id"],
                status=result["status"],
            )
        finally:
            conn.close()

    def StreamSellOrders(self, request, context):
        from services.grpc import ecocredit_pb2
        conn = self._get_conn()
        try:
            last_check = int(time.time())
            while context.is_active():
                time.sleep(5)
                now = int(time.time())
                orders = conn.execute(
                    conn.text(
                        "SELECT id, seller_address, quantity, ask_price, status, updated_at "
                        "FROM credit_sell_order WHERE updated_at > :last_check ORDER BY updated_at"
                    ),
                    {"last_check": last_check},
                ).mappings().all()
                for o in orders:
                    yield ecocredit_pb2.SellOrderUpdate(
                        order_id=str(o["id"]),
                        seller_address=o["seller_address"],
                        quantity=float(o["quantity"]),
                        ask_price=float(o["ask_price"]),
                        status=o["status"],
                        timestamp=int(o["updated_at"].timestamp()) if o["updated_at"] else now,
                    )
                last_check = now
        finally:
            conn.close()

    # --- Allowed Denoms ---

    def AllowedDenoms(self, request, context):
        from services.grpc import ecocredit_pb2
        conn = self._get_conn()
        try:
            from services.credit_class.marketplace import list_allowed_denoms
            denoms = list_allowed_denoms(conn)
            return ecocredit_pb2.AllowedDenomsResponse(
                allowed_denoms=[ecocredit_pb2.AllowedDenom(
                    id=d["id"], denom=d["denom"], chain=d.get("chain", ""),
                    is_active=d["is_active"],
                ) for d in denoms]
            )
        finally:
            conn.close()

    # --- Fee Params ---

    def GetFeeParams(self, request, context):
        from services.grpc import ecocredit_pb2
        conn = self._get_conn()
        try:
            from services.credit_class.marketplace import get_fee_params
            params = get_fee_params(conn)
            return ecocredit_pb2.GetFeeParamsResponse(
                fee_params=ecocredit_pb2.FeeParams(
                    buyer_fee=params["buyer_fee"],
                    seller_fee=params["seller_fee"],
                )
            )
        finally:
            conn.close()

    # --- Bridge ---

    def BridgeOut(self, request, context):
        from services.grpc import ecocredit_pb2
        conn = self._get_conn()
        try:
            from services.credit_class.bridge import create_bridge_outbound
            result = create_bridge_outbound(
                conn, credit_batch_id=request.credit_batch_id,
                sender_address=request.sender_address,
                target_chain=request.target_chain,
                recipient_address=request.recipient_address,
                quantity=request.quantity,
            )
            return ecocredit_pb2.BridgeOutResponse(bridge_tx_id=result["id"])
        finally:
            conn.close()

    def BridgeIn(self, request, context):
        from services.grpc import ecocredit_pb2
        conn = self._get_conn()
        try:
            from services.credit_class.bridge import create_bridge_inbound
            result = create_bridge_inbound(
                conn, credit_class_id=request.credit_class_id,
                source_chain=request.source_chain,
                issuer_address=request.issuer_address,
                recipient_address=request.recipient_address,
                quantity=request.quantity,
                origin_tx_id=request.origin_tx_id or None,
            )
            return ecocredit_pb2.BridgeInResponse(bridge_tx_id=result["id"])
        finally:
            conn.close()

    def BridgeComplete(self, request, context):
        from services.grpc import ecocredit_pb2
        conn = self._get_conn()
        try:
            from services.credit_class.bridge import complete_bridge
            result = complete_bridge(conn, request.bridge_tx_id, request.bridge_tx_hash or None)
            return ecocredit_pb2.BridgeCompleteResponse(status=result["status"])
        finally:
            conn.close()

    # --- Enrollment ---

    def ApplyToClass(self, request, context):
        from services.grpc import ecocredit_pb2
        conn = self._get_conn()
        try:
            from services.credit_class.enrollment import apply_to_class
            result = apply_to_class(
                conn, location_id=request.location_id,
                credit_class_id=request.credit_class_id,
                application_metadata=request.application_metadata or None,
            )
            return ecocredit_pb2.ApplyToClassResponse(
                enrollment_id=result["id"], status=result["status"],
            )
        finally:
            conn.close()

    def EvaluateApplication(self, request, context):
        from services.grpc import ecocredit_pb2
        conn = self._get_conn()
        try:
            from services.credit_class.enrollment import evaluate_application
            result = evaluate_application(
                conn, enrollment_id=request.enrollment_id,
                issuer_address=request.issuer_address,
                new_status=request.new_status,
                enrollment_metadata=request.enrollment_metadata or None,
            )
            return ecocredit_pb2.EvaluateApplicationResponse(
                enrollment_id=result["enrollment_id"],
                old_status=result["old_status"],
                new_status=result["new_status"],
            )
        finally:
            conn.close()

    def ListEnrollments(self, request, context):
        from services.grpc import ecocredit_pb2
        conn = self._get_conn()
        try:
            from services.credit_class.enrollment import list_enrollments_by_project, list_enrollments_by_class
            if request.location_id:
                enrollments = list_enrollments_by_project(conn, request.location_id)
            elif request.class_id:
                enrollments = list_enrollments_by_class(conn, request.class_id)
            else:
                enrollments = []
            return ecocredit_pb2.ListEnrollmentsResponse(
                enrollments=[ecocredit_pb2.Enrollment(
                    id=e["id"], location_id=str(e["location_id"]),
                    credit_class_id=str(e["credit_class_id"]),
                    status=e["status"],
                ) for e in enrollments]
            )
        finally:
            conn.close()

    # --- Credit Types ---

    def CreditTypes(self, request, context):
        from services.grpc import ecocredit_pb2
        conn = self._get_conn()
        try:
            from services.credit_class.entities import list_credit_types
            types = list_credit_types(conn)
            return ecocredit_pb2.CreditTypesResponse(
                credit_types=[ecocredit_pb2.CreditType(
                    abbreviation=t["abbreviation"], name=t["name"],
                    unit=t["unit"], precision=t["precision"],
                    description=t.get("description", ""),
                ) for t in types]
            )
        finally:
            conn.close()
