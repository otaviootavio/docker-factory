from fastapi import APIRouter, HTTPException
from src.container_manager import SecureGCPContainerManager
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/")
async def create_deployment(client_id: str):
    try:
        manager = SecureGCPContainerManager(client_id)
        deployment_info = manager.deploy()
        return deployment_info
    except Exception as e:
        logger.error(f"Deployment failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{service_name}")
async def get_deployment(service_name: str):
    try:
        manager = SecureGCPContainerManager("system")
        service_info = manager.cloud_run_service.get_service_info(
            service_name=service_name,
            region="us-central1"
        )
        return service_info
    except Exception as e:
        logger.error(f"Failed to get deployment: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
