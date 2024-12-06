from fastapi import APIRouter, HTTPException, Query
from src.container_manager import SecureGCPContainerManager
import logging
import re
from pydantic import BaseModel, Field, field_validator

router = APIRouter()
logger = logging.getLogger(__name__)


class DeploymentRequest(BaseModel):
    client_id: str = Field(..., description="Client identifier")

    @field_validator("client_id")
    def validate_client_id(cls, value: str) -> str:
        import re

        if not re.match(r"^[a-z0-9][a-z0-9_-]*$", value.lower()):
            raise ValueError("client_id must contain only lowercase letters, numbers, hyphens, and underscores")
        return value.lower()


@router.post("/")
async def create_deployment(request: DeploymentRequest):
    try:
        manager = SecureGCPContainerManager(request.client_id)
        return manager.deploy()
    except Exception as e:
        logger.error(f"Deployment failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{service_name}")
async def get_deployment(service_name: str):
    try:
        manager = SecureGCPContainerManager("system")
        service_info = manager.cloud_run_service.get_service_info(service_name=service_name, region="us-central1")
        return service_info
    except Exception as e:
        logger.error(f"Failed to get deployment: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
