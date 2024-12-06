from datetime import datetime
import random
import string
from pathlib import Path

from .clients.gcp_client import GCPClient
from .clients.docker_client import DockerClient
from .services.artifact_service import ArtifactService
from .services.cloud_run_service import CloudRunService
from .services.container_service import ContainerService
from .utils.security import SecurityUtils
from .utils.logging import setup_logging
from . import db
import shutil

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
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        random_suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
        self.unique_id = f"{timestamp}-{random_suffix}"

        # Set up deployment variables
        self.region = "us-central1"
        repo_name = self.client_id.split("@")[0].lower().replace("_", "-")
        self.repository_name = f"secure-app-{repo_name}"
        self.registry_location = f"{self.region}-docker.pkg.dev"
        self.image_name = "secure-app"
        self.service_name = f"secure-app-{self.unique_id}"

        # Build image tag components
        registry = self.registry_location
        project = self.gcp_client.project_id
        repo = self.repository_name
        image = self.image_name
        tag = self.unique_id

        # Combine components into full image tag
        self.image_tag = f"{registry}/{project}/{repo}/{image}:{tag}"

    def deploy(self):
        """Main deployment orchestration"""
        app_dir = None  # Track app directory for cleanup
        try:
            logger.info(
                f"Starting secure deployment for client: {self.client_id}")

            # Create app files
            app_dir = self.container_service.create_app_files(self.unique_id)
            logger.info(f"App files created at: {app_dir}")

            # Build and push container
            self.container_service.build_container(app_dir, self.image_tag)
            self.artifact_service.create_repository(self.repository_name, self.region)
            self.artifact_service.push_to_registry(self.image_tag, self.registry_location)

            # Deploy to Cloud Run
            deployment_result = self.cloud_run_service.deploy(
                self.service_name,
                self.image_tag,
                self.region,
                self.security.get_env_vars(),
            )

            # Generate deployment info
            service_info = self.cloud_run_service.get_service_info(self.service_name, self.region)

            # Add database storage
            deployment_info = {
                **service_info,
                "image_tag": self.image_tag,
                "access_token": self.security.generate_access_token(),
                "deployment_time": datetime.now().isoformat(),
            }

            # Store in database
            db.save_deployment(deployment_info, self.client_id)

            return deployment_info

        except Exception as e:
            logger.error(f"Secure deployment workflow failed: {e}")
            raise

        finally:
            if app_dir:
                try:
                    logger.info(f"Attempting to remove app files at: {app_dir}")
                    self.remove_app_files(app_dir)
                    logger.info(f"App files cleaned up successfully: {app_dir}")
                except Exception as cleanup_error:
                    logger.warning(
                        f"Failed to remove app files: {cleanup_error}")

    def remove_app_files(self, app_dir):
        """Remove app files after deployment"""
        try:
            path = Path(app_dir)
            if path.exists() and path.is_dir():
                shutil.rmtree(path)
                logger.info(f"Removed app files at: {app_dir}")
            else:
                logger.warning(f"App directory not found or not a directory: {app_dir}")
        except Exception as e:
            logger.error(f"Error cleaning up app files at {app_dir}: {e}")
            raise
