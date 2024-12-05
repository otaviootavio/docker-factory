from google.cloud import run_v2
from google.cloud import artifactregistry_v1
import google.auth
from pathlib import Path
import docker
import logging
from datetime import datetime
import random
import string
import subprocess
import time
import pkg_resources

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GCPContainerManager:
    def __init__(self):
        # Initialize clients
        self.cloud_run_client = run_v2.ServicesClient()
        self.artifact_client = artifactregistry_v1.ArtifactRegistryClient()
        self.docker_client = docker.from_env()
        
        # Log versions for diagnostics
        self.check_dependencies()
        
        # Get default credentials and project
        self.credentials, self.project_id = google.auth.default()
        
        # Generate unique identifiers
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
        self.unique_id = f"{timestamp}-{random_suffix}"
        
        # Set up variables with unique names
        self.region = 'us-central1'
        self.repository_name = 'hello-world'  # Define repository_name first
        self.registry_location = f'{self.region}-docker.pkg.dev'
        self.image_name = 'app'
        self.service_name = f'hello-world-{self.unique_id}'
        
        # Set image tag last, after all required attributes are defined
        self.image_tag = f'{self.registry_location}/{self.project_id}/{self.repository_name}/{self.image_name}:{self.unique_id}'
        
    def check_dependencies(self):
        """Log dependency versions"""
        deps = ['google-cloud-run', 'google-cloud-artifactregistry', 'docker']
        for dep in deps:
            try:
                version = pkg_resources.get_distribution(dep).version
                logger.info(f"{dep} version: {version}")
            except Exception as e:
                logger.warning(f"Could not get version for {dep}: {e}")

    def create_app_files(self):
        """Create necessary application files"""
        app_dir = Path(f'hello-world-app-{self.unique_id}')
        app_dir.mkdir(exist_ok=True)
        
        # Write Flask application with unique identifier
        app_content = f"""
from flask import Flask
app = Flask(__name__)

@app.route('/')
def hello():
    return 'Hello, World! from {self.service_name}'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
"""
        (app_dir / 'app.py').write_text(app_content)
        
        # Write Dockerfile
        dockerfile_content = """
FROM python:3.9-slim
WORKDIR /app
COPY . .
RUN pip install flask
EXPOSE 8080
CMD ["python", "app.py"]
"""
        (app_dir / 'Dockerfile').write_text(dockerfile_content)
        
        return app_dir

    def build_container(self, app_dir):
        """Build container using Docker SDK"""
        try:
            logger.info("Building container image...")
            self.docker_client.images.build(
                path=str(app_dir),
                tag=self.image_tag,
                rm=True
            )
            logger.info("Container build completed")
        except docker.errors.BuildError as e:
            logger.error(f"Failed to build container: {e}")
            raise

    def push_to_artifact_registry(self):
        """Push container to Artifact Registry using Docker SDK"""
        try:
            logger.info("Pushing container to Artifact Registry...")
            auth_config = {
                "username": "_json_key",
                "password": self.credentials.token
            }
            self.docker_client.images.push(
                self.image_tag,
                auth_config=auth_config
            )
            logger.info("Container pushed successfully")
        except docker.errors.APIError as e:
            logger.error(f"Failed to push container: {e}")
            raise

    def deploy_to_cloud_run(self):
        """Deploy container to Cloud Run"""
        try:
            logger.info(f"Deploying service to Cloud Run: {self.service_name}")
            
            # Initialize request argument(s)
            service = run_v2.Service()
            service.template = run_v2.RevisionTemplate()
            
            # Set container configuration
            container = run_v2.Container()
            container.image = self.image_tag
            port = run_v2.ContainerPort()
            port.container_port = 8080
            container.ports = [port]
            
            # Set template and service configuration
            service.template.containers = [container]
            
            # Create service request
            request = run_v2.CreateServiceRequest(
                parent=f"projects/{self.project_id}/locations/{self.region}",
                service_id=self.service_name,
                service=service,
            )
            
            # Make the request
            operation = self.cloud_run_client.create_service(request=request)
            result = operation.result()  # Wait for operation to complete
            
            logger.info(f"Service deployed successfully: {result.uri}")
            return result
                
        except Exception as e:
            logger.error(f"Failed to deploy to Cloud Run: {e}")
            raise

    def get_service_info(self):
        """Retrieve Cloud Run service information"""
        try:
            # Initialize request argument(s)
            request = run_v2.GetServiceRequest(
                name=f"projects/{self.project_id}/locations/{self.region}/services/{self.service_name}"
            )
            
            # Make the request
            service = self.cloud_run_client.get_service(request=request)
            
            # Process the response
            service_info = {
                'service_name': self.service_name,
                'image_tag': self.image_tag,
                'uri': service.uri,
                'region': self.region,
                'latest_created_revision': service.latest_created_revision,
            }
            
            return service_info
                
        except Exception as e:
            logger.error(f"Failed to retrieve service info: {e}")
            raise
        
    def create_artifact_repository(self):
        """Create Artifact Registry repository if it doesn't exist"""
        try:
            logger.info(f"Creating/checking Artifact Registry repository: {self.repository_name}")
            
            # Format the repository path
            repository_path = f"projects/{self.project_id}/locations/{self.region}/repositories/{self.repository_name}"
            
            try:
                # Try to get the repository first
                request = artifactregistry_v1.GetRepositoryRequest(name=repository_path)
                self.artifact_client.get_repository(request=request)
                logger.info("Repository already exists")
            except Exception:
                # Repository doesn't exist, create it
                parent = f"projects/{self.project_id}/locations/{self.region}"
                
                repository = artifactregistry_v1.Repository()
                repository.format_ = artifactregistry_v1.Repository.Format.DOCKER
                repository.description = "Docker repository for hello-world application"
                
                request = artifactregistry_v1.CreateRepositoryRequest(
                    parent=parent,
                    repository_id=self.repository_name,
                    repository=repository
                )
                
                operation = self.artifact_client.create_repository(request=request)
                operation.result()  # Wait for operation to complete
                logger.info("Repository created successfully")
                
                # Configure Docker authentication
                subprocess.run([
                    'gcloud', 'auth', 'configure-docker', 
                    f'{self.region}-docker.pkg.dev'
                ], check=True)
                
        except Exception as e:
            logger.error(f"Failed to create repository: {e}")
            raise
    
    def verify_image_exists(self):
        """Verify that the image exists in Artifact Registry"""
        try:
            logger.info(f"Verifying image existence: {self.image_tag}")
            
            # Use gcloud command to list images instead of describe
            result = subprocess.run([
                'gcloud', 'artifacts', 'docker', 'images', 'list',
                f'{self.registry_location}/{self.project_id}/{self.repository_name}',
                f'--filter=tags:{self.unique_id}',
                '--format=json',
                '--quiet'
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                raise Exception(f"Failed to list images: {result.stderr}")
                
            if result.stdout.strip():
                logger.info("Image verified in registry")
                return True
            
            logger.info("Image not found in registry")
            return False
            
        except Exception as e:
            logger.error(f"Image verification failed: {e}")
            return False

    def push_to_artifact_registry(self):
        """Push container to Artifact Registry using Docker SDK"""
        try:
            logger.info("Pushing container to Artifact Registry...")
            
            # Configure Docker credentials
            subprocess.run([
                'gcloud', 'auth', 'configure-docker', 
                self.registry_location,
                '--quiet'
            ], check=True)
            
            logger.info(f"Pushing image: {self.image_tag}")
            # Push the image
            result = self.docker_client.images.push(self.image_tag)
            logger.info("Container pushed successfully")
            
            # Verify the image exists with retries
            retry_count = 0
            while retry_count < 3:
                if self.verify_image_exists():
                    return
                logger.info(f"Waiting for image to be available (attempt {retry_count + 1}/3)")
                time.sleep(10)
                retry_count += 1
                
            raise Exception("Image not available after retries")
            
        except Exception as e:
            logger.error(f"Failed to push container: {e}")
            raise
    
def main():
    try:
        manager = GCPContainerManager()
        logger.info(f"Starting deployment with unique ID: {manager.unique_id}")
        
        app_dir = manager.create_app_files()
        manager.build_container(app_dir)
        manager.create_artifact_repository()  # Add this line
        manager.push_to_artifact_registry()
        manager.deploy_to_cloud_run()
        
        service_info = manager.get_service_info()
        logger.info(f"Service Information: {service_info}")
        
        return service_info
        
    except Exception as e:
        logger.error(f"Workflow failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Workflow failed: {e}")
        raise

if __name__ == "__main__":
    main()