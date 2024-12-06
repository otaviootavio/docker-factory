from pydantic import BaseModel, Field
from typing import Optional, Dict, List
from datetime import datetime


class DeploymentRequest(BaseModel):
    client_id: str = Field(..., description="Client identifier")
    region: str = Field(default="us-central1", description="Deployment region")
    environment_vars: Optional[Dict[str, str]] = Field(default={}, description="Additional environment variables")


class DeploymentResponse(BaseModel):
    service_name: str
    rpc_endpoint: str
    ws_endpoint: str
    status: str
    connection_examples: Dict[str, str]
    access_token: str
    deployment_time: datetime


class DeploymentStatus(BaseModel):
    service_name: str
    status: str
    last_updated: datetime


class DeploymentList(BaseModel):
    deployments: List[DeploymentStatus]
    total: int
    page: int
    page_size: int
