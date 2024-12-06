import logging
import subprocess
import time
import google.api_core.exceptions
from google.cloud import artifactregistry_v1

logger = logging.getLogger(__name__)

class ArtifactService:
    def __init__(self, gcp_client, docker_client):
        self.gcp_client = gcp_client
        self.docker_client = docker_client

    def create_repository(self, repository_name, region):
        try:
            logger.info(f"Creating/checking Artifact Registry repository: {repository_name}")
            
            parent = f"projects/{self.gcp_client.project_id}/locations/{region}"
            repository_path = f"{parent}/repositories/{repository_name}"
            
            try:
                get_request = artifactregistry_v1.GetRepositoryRequest(
                    name=repository_path
                )
                existing_repo = self.gcp_client.artifact_client.get_repository(
                    request=get_request)
                logger.info("Repository already exists")
                return existing_repo
                
            except google.api_core.exceptions.NotFound:
                logger.info("Repository not found, creating new one...")
                
                repository = artifactregistry_v1.Repository()
                repository.format_ = artifactregistry_v1.Repository.Format.DOCKER
                repository.description = f"Docker repository for secure applications"
                
                create_request = artifactregistry_v1.CreateRepositoryRequest(
                    parent=parent,
                    repository_id=repository_name,
                    repository=repository
                )
                
                operation = self.gcp_client.artifact_client.create_repository(
                    request=create_request)
                result = operation.result()
                
                self._configure_docker_auth(region)
                return result
                
        except Exception as e:
            logger.error(f"Failed to create repository: {e}")
            raise

    def push_to_registry(self, image_tag, registry_location):
        try:
            logger.info("Pushing container to Artifact Registry...")
            
            self._configure_docker_auth(registry_location)
            
            self.docker_client.push_image(image_tag)
            
            retry_count = 0
            while retry_count < 3:
                if self._verify_image_exists(image_tag):
                    return
                logger.info(f"Waiting for image to be available (attempt {retry_count + 1}/3)")
                time.sleep(10)
                retry_count += 1
                
            raise Exception("Image not available after retries")
            
        except Exception as e:
            logger.error(f"Failed to push container: {e}")
            raise

    def _configure_docker_auth(self, location):
        auth_result = subprocess.run([
            'gcloud', 'auth', 'configure-docker',
            location,
            '--quiet'
        ], capture_output=True, text=True)
        
        if auth_result.returncode != 0:
            raise Exception(f"Failed to configure Docker authentication: {auth_result.stderr}")

    def _verify_image_exists(self, image_tag):
        try:
            result = subprocess.run([
                'gcloud', 'artifacts', 'docker', 'images', 'list',
                image_tag,
                '--format=json',
                '--quiet'
            ], capture_output=True, text=True)
            
            return result.returncode == 0 and bool(result.stdout.strip())
            
        except Exception as e:
            logger.error(f"Image verification failed: {e}")
            return False
