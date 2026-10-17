"""Database-independent EAS GraphQL contract shared by scheduled workers."""

from __future__ import annotations

from services.common.http import http

EAS_ENDPOINTS = {
    "optimism": "https://optimism.easscan.org",
    "base": "https://base.easscan.org",
    "celo": "https://celo.easscan.org",
}

ATTESTATIONS_BY_RECIPIENT = """
query GetAttestations($recipient: String!, $after: Int!) {
    attestations(
        where: { recipient: { equals: $recipient } }
        orderBy: { time: desc }
        take: 100
        skip: $after
    ) {
        id
        txid
        schema { id schema }
        attester
        recipient
        data
        time
        timeCreated
        revocable
        revoked
        expirationTime
    }
}
"""

SCHEMAS_BY_CREATOR = """
query GetSchemas($creator: String!, $after: Int!) {
    schemata(
        where: { creator: { equals: $creator } }
        orderBy: { time: desc }
        take: 100
        skip: $after
    ) {
        id
        schema
        creator
        resolver
        revocable
        time
        txid
    }
}
"""


class EASProviderQueryError(RuntimeError):
    """The EAS GraphQL endpoint returned an unusable query response."""


def execute_eas_query(chain: str, query: str, variables: dict) -> dict:
    """Execute one EAS GraphQL request without importing database helpers."""
    endpoint = EAS_ENDPOINTS.get(chain)
    if not endpoint:
        raise ValueError(f"No EAS endpoint configured for chain: {chain}")
    response = http.post(
        f"{endpoint}/graphql",
        json={"query": query, "variables": variables},
        timeout=30,
        headers={"Content-Type": "application/json"},
    )
    try:
        response.raise_for_status()
        try:
            payload = response.json()
        except (TypeError, ValueError):
            raise EASProviderQueryError("EAS provider returned invalid JSON") from None
        if not isinstance(payload, dict):
            raise EASProviderQueryError("EAS provider returned an invalid response")
        if payload.get("errors"):
            # Do not persist partial GraphQL data: a cursor could otherwise
            # advance past attestations omitted by a partially failed query.
            raise EASProviderQueryError("EAS GraphQL query failed")
        data = payload.get("data")
        if not isinstance(data, dict):
            raise EASProviderQueryError("EAS provider response has no data object")
        return data
    finally:
        response.close()
