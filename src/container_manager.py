from datetime import datetime
import random
import string
import logging
from pathlib import Path

from .clients.gcp_client import GCPClient
from .clients.docker_client import DockerClient
from .services.artifact_service import ArtifactService
from .services.cloud_run_service import CloudRunService
from .services.container_service import ContainerService
from .utils.security import SecurityUtils
from .utils.logging import setup_logging

logger = setup_logging(__name__)

class SecureGCPContainerManager:
    def __init__(self, client_id):
        self.client_id = client_id
        
        # Initialize security utils
        self.security = SecurityUtils(client_id)
        
        # Initialize clients
        self.gcp_client = GCPClient()
        self.docker_client = DockerClient()
        
        # Initialize services
        self.artifact_service = ArtifactService(self.gcp_client, self.docker_client)
        self.cloud_run_service = CloudRunService(self.gcp_client)
        self.container_service = ContainerService(self.docker_client)
        
        # Set up unique identifiers
        self._setup_identifiers()
        
    def _setup_identifiers(self):
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        random_suffix = ''.join(random.choices(
            string.ascii_lowercase + string.digits, k=4))
        self.unique_id = f"{timestamp}-{random_suffix}"
        
        # Set up deployment variables
        self.region = 'us-central1'
        self.repository_name = f'secure-app-{self.client_id.split("@")[0]}'
        self.registry_location = f'{self.region}-docker.pkg.dev'
        self.image_name = 'secure-app'
        self.service_name = f'secure-app-{self.unique_id}'
        self.image_tag = (f'{self.registry_location}/{self.gcp_client.project_id}/'
                         f'{self.repository_name}/{self.image_name}:{self.unique_id}')

    def deploy(self):
        """Main deployment orchestration"""
        try:
            logger.info(f"Starting secure deployment for client: {self.client_id}")
            
            # Create app files
            app_dir = self.container_service.create_app_files(self.unique_id)
            
            # Build and push container
            self.container_service.build_container(app_dir, self.image_tag)
            self.artifact_service.create_repository(self.repository_name, self.region)
            self.artifact_service.push_to_registry(self.image_tag, self.registry_location)
            
            # Deploy to Cloud Run
            deployment_result = self.cloud_run_service.deploy(
                self.service_name,
                self.image_tag,
                self.region,
                self.security.get_env_vars()
            )
            
            # Generate deployment info
            service_info = self.cloud_run_service.get_service_info(
                self.service_name,
                self.region
            )
            
            return {
                **service_info,
                'access_token': self.security.generate_access_token(),
                'deployment_time': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Secure deployment workflow failed: {e}")
            raise
