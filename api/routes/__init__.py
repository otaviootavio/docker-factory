"""
API Routes module
"""

from .deployments import router as deployment_router

__all__ = ["deployment_router"]
