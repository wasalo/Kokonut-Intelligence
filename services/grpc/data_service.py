"""Data module gRPC service implementation."""

from __future__ import annotations

import json
import time

import grpc

from services.common.logging import get_logger

logger = get_logger("grpc.data_service")


class DataServiceServicer:
    """Data module service implementing gRPC RPCs."""

    def __init__(self, db_factory):
        self._db_factory = db_factory

    def _get_conn(self):
        return self._db_factory()

    def GenerateIRI(self, request, context):
        from services.grpc.data.v1 import types_pb2 as data_pb2
        conn = self._get_conn()
        try:
            from services.iri.resolver import generate_iri
            metadata = json.loads(request.metadata_json) if request.metadata_json else None
            iri = generate_iri(
                conn, entity_type=request.entity_type, entity_id=request.entity_id,
                content=metadata, content_hash_type=request.content_hash_type or "raw",
                algorithm=request.algorithm or "sha256",
            )
            return data_pb2.GenerateIRIResponse(iri=iri)
        finally:
            conn.close()

    def ResolveIRI(self, request, context):
        from services.grpc.data.v1 import types_pb2 as data_pb2
        from services.common.logging import get_logger
        conn = self._get_conn()
        try:
            from services.iri.resolver import resolve_metadata
            result = resolve_metadata(conn, request.iri)
            if not result:
                context.abort(grpc.StatusCode.NOT_FOUND, f"IRI not found: {request.iri}")
            return data_pb2.ResolveIRIResponse(
                iri_info=data_pb2.IRI(
                    iri=result["iri"], entity_type=result["entity_type"],
                    entity_id=result["entity_id"], version=result["version"],
                    content_hash=result.get("content_hash", ""),
                )
            )
        finally:
            conn.close()

    def GetVersionHistory(self, request, context):
        from services.grpc.data.v1 import types_pb2 as data_pb2
        conn = self._get_conn()
        try:
            from services.iri.resolver import get_version_history
            versions = get_version_history(conn, request.entity_type, request.entity_id)
            return data_pb2.GetVersionHistoryResponse(
                versions=[data_pb2.IRI(
                    iri=v["iri"], version=v["version"],
                    content_hash=v.get("content_hash", ""),
                ) for v in versions]
            )
        finally:
            conn.close()

    def ComputeContentHash(self, request, context):
        from services.grpc.data.v1 import types_pb2 as data_pb2
        from services.data_module.content_hash import compute_content_hash
        result = compute_content_hash(
            request.data, algorithm=request.algorithm or "sha256",
            content_type=request.content_type or "raw",
            media_type=request.media_type or None,
        )
        return data_pb2.ComputeContentHashResponse(**result)

    def CreateContentHash(self, request, context):
        from services.grpc.data.v1 import types_pb2 as data_pb2
        conn = self._get_conn()
        try:
            from services.data_module.content_hash import create_content_hash
            result = create_content_hash(
                conn, iri_id=request.iri_id, hash_value=request.hash_value,
                hash_algorithm=request.hash_algorithm or "sha256",
                content_type=request.content_type or "raw",
                media_type=request.media_type or None,
                canonicalization_algorithm=request.canonicalization_algorithm or None,
                merkle_tree=request.merkle_tree or "none",
            )
            return data_pb2.CreateContentHashResponse(**result)
        finally:
            conn.close()

    def FindIRIByHash(self, request, context):
        from services.grpc.data.v1 import types_pb2 as data_pb2
        conn = self._get_conn()
        try:
            from services.data_module.content_hash import find_iri_by_content_hash
            results = find_iri_by_content_hash(conn, request.hash_value)
            return data_pb2.FindIRIByHashResponse(
                results=[data_pb2.IRIInfo(
                    iri=r["iri"], entity_type=r["entity_type"],
                    entity_id=str(r["entity_id"]),
                    content_hash=r.get("hash_value", ""),
                    hash_algorithm=r.get("hash_algorithm", ""),
                ) for r in results]
            )
        finally:
            conn.close()

    def DefineResolver(self, request, context):
        from services.grpc.data.v1 import types_pb2 as data_pb2
        conn = self._get_conn()
        try:
            from services.data_module.resolver import define_resolver
            result = define_resolver(conn, request.resolver_url, request.manager_address,
                                     request.description or None)
            return data_pb2.DefineResolverResponse(**result)
        finally:
            conn.close()

    def RegisterToResolver(self, request, context):
        from services.grpc.data.v1 import types_pb2 as data_pb2
        conn = self._get_conn()
        try:
            from services.data_module.resolver import register_data_to_resolver
            result = register_data_to_resolver(conn, request.resolver_id, request.iri_id,
                                                request.registered_by or None)
            return data_pb2.RegisterToResolverResponse(**result)
        finally:
            conn.close()

    def GetResolversForIRI(self, request, context):
        from services.grpc.data.v1 import types_pb2 as data_pb2
        conn = self._get_conn()
        try:
            from services.data_module.resolver import get_resolvers_for_iri
            resolvers = get_resolvers_for_iri(conn, request.iri_id)
            return data_pb2.GetResolversForIRIResponse(
                resolvers=[data_pb2.Resolver(
                    id=r["id"], resolver_url=r["resolver_url"],
                    manager_address=r["manager_address"],
                    is_active=r["is_active"],
                ) for r in resolvers]
            )
        finally:
            conn.close()

    def ListResolvers(self, request, context):
        from services.grpc.data.v1 import types_pb2 as data_pb2
        conn = self._get_conn()
        try:
            from services.data_module.resolver import list_resolvers
            resolvers = list_resolvers(conn, request.manager_address or None)
            return data_pb2.ListResolversResponse(
                resolvers=[data_pb2.Resolver(
                    id=r["id"], resolver_url=r["resolver_url"],
                    manager_address=r["manager_address"],
                    is_active=r["is_active"],
                ) for r in resolvers]
            )
        finally:
            conn.close()

    def AttestToIRI(self, request, context):
        from services.grpc.data.v1 import types_pb2 as data_pb2
        conn = self._get_conn()
        try:
            from services.data_module.attestor import attest_to_iri
            result = attest_to_iri(conn, request.iri_id, request.attestor_address)
            return data_pb2.AttestToIRIResponse(**result)
        finally:
            conn.close()

    def GetAttestorsForIRI(self, request, context):
        from services.grpc.data.v1 import types_pb2 as data_pb2
        conn = self._get_conn()
        try:
            from services.data_module.attestor import get_attestors_for_iri
            attestors = get_attestors_for_iri(conn, request.iri_id)
            return data_pb2.GetAttestorsForIRIResponse(
                attestors=[data_pb2.AttestorEntry(
                    id=a["id"], iri_id=str(a["iri_id"]),
                    attestor_address=a["attestor_address"],
                ) for a in attestors]
            )
        finally:
            conn.close()

    def StreamNewIRIs(self, request, context):
        from services.grpc.data.v1 import types_pb2 as data_pb2
        conn = self._get_conn()
        try:
            last_check = int(time.time())
            while context.is_active():
                time.sleep(5)
                now = int(time.time())
                iris = conn.execute(
                    conn.text(
                        "SELECT iri, entity_type, entity_id, version, content_hash, created_at "
                        "FROM iri_registry WHERE created_at > :last_check ORDER BY created_at"
                    ),
                    {"last_check": last_check},
                ).mappings().all()
                for iri in iris:
                    yield data_pb2.IRIUpdate(
                        iri=iri["iri"],
                        entity_type=iri["entity_type"],
                        entity_id=str(iri["entity_id"]),
                        version=iri["version"],
                        content_hash=iri.get("content_hash", ""),
                        timestamp=int(iri["created_at"].timestamp()) if iri["created_at"] else now,
                    )
                last_check = now
        finally:
            conn.close()
