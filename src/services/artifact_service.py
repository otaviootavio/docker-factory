import logging
import requests
import subprocess
import time
import google.api_core.exceptions
from google.cloud import artifactregistry_v1
import jwt

logger = logging.getLogger(__name__)


class ArtifactService:
    def __init__(self, gcp_client, docker_client):
        self.gcp_client = gcp_client
        self.docker_client = docker_client
        self.artifact_client = gcp_client.artifact_client

    def create_repository(self, repository_name, region):
        """Create Artifact Registry repository"""
        try:
            logger.info(
                f"Creating/checking Artifact Registry repository: {repository_name}")

            parent = f"projects/{self.gcp_client.project_id}/locations/{region}"
            repository_path = f"{parent}/repositories/{repository_name}"

            try:
                # Try to get existing repository
                request = artifactregistry_v1.GetRepositoryRequest(
                    name=repository_path)
                return self.artifact_client.get_repository(request=request)
            except Exception:
                # Create new repository if it doesn't exist
                logger.info("Repository not found, creating new one...")
                repository = artifactregistry_v1.Repository()
                repository.format_ = artifactregistry_v1.Repository.Format.DOCKER

                request = artifactregistry_v1.CreateRepositoryRequest(
                    parent=parent,
                    repository_id=repository_name,
                    repository=repository
                )
                operation = self.artifact_client.create_repository(
                    request=request)
                return operation.result()

        except Exception as e:
            logger.error(f"Failed to create repository: {e}")
            raise

    def _get_docker_auth_token(self, registry):
        # Generate short-lived token for Docker authentication
        token = jwt.encode(
            {
                'iat': time.time(),
                'exp': time.time() + 3600,
                'aud': 'https://oauth2.googleapis.com/token',
                'iss': self.gcp_client.credentials.service_account_email,
                'target_audience': registry
            },
            self.gcp_client.credentials.private_key,
            algorithm='RS256'
        )

        # Exchange JWT for OAuth2 token
        auth_req = requests.Request()
        token_response = auth_req.post(
            'https://oauth2.googleapis.com/token',
            data={
                'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
                'assertion': token
            }
        )

        return token_response.json()['access_token']

    def push_to_registry(self, image_tag, registry_location):
        """Push container to Artifact Registry"""
        try:
            logger.info("Pushing container to Artifact Registry...")

            # Get authentication token
            auth_request = google.auth.transport.requests.Request()
            self.gcp_client.credentials.refresh(auth_request)
            token = self.gcp_client.credentials.token

            # Configure Docker with correct registry URL
            registry_url = f"https://{registry_location}"
            self.docker_client.client.login(
                username='oauth2accesstoken',
                password=token,
                registry=registry_url
            )

            # Push image
            result = self.docker_client.push_image(image_tag)
            logger.info(f"Successfully pushed image: {image_tag}")
            return result

        except Exception as e:
            logger.error(f"Failed to push container: {e}")
            raise

    def _configure_docker_auth(self, registry_location):
        """Configure Docker authentication using GCP credentials"""
        try:
            # Create auth request
            auth_request = google.auth.transport.requests.Request()

            # Refresh credentials if needed
            self.gcp_client.credentials.refresh(auth_request)

            # Get the token
            token = self.gcp_client.credentials.token

            # Configure Docker client with token
            self.docker_client.client.login(
                username='oauth2accesstoken',
                password=token,
                registry=registry_location
            )

            logger.info(f"Successfully configured Docker authentication for {
                        registry_location}")

        except Exception as e:
            logger.error(f"Failed to configure Docker authentication: {e}")
            raise

    def _verify_image_exists(self, image_tag):
        try:
            # Parse repository and image details from tag
            project = self.gcp_client.project_id
            repository = image_tag.split('/')[-2]
            image = image_tag.split('/')[-1]

            # Get the parent path for the repository
            location = image_tag.split('-docker.pkg.dev')[0].split('/')[-1]
            parent = f"projects/{project}/locations/{
                location}/repositories/{repository}"

            # List images in repository
            request = self.gcp_client.artifact_client.list_docker_images(
                parent=parent
            )

            # Check if our image exists
            try:
                for image_item in request:
                    if image in image_item.uri:
                        return True
                return False
            except Exception as e:
                logger.error(f"Error checking image existence: {e}")
                return False

        except Exception as e:
            logger.error(f"Image verification failed: {e}")
            return False
