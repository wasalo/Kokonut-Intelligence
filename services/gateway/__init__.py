"""Unified API Gateway — single entry point for all API traffic."""

from services.gateway.app import create_app

__all__ = ["create_app"]
