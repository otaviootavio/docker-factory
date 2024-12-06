from importlib.metadata import version as pkg_version
from google.cloud import run_v2
from google.cloud import artifactregistry_v1
from google.api_core import operation
from google.iam.v1 import iam_policy_pb2
from google.iam.v1 import policy_pb2
import google.auth
import docker
import logging
from datetime import datetime, timedelta, timezone
import random
import string
import secrets
import jwt
import subprocess
import time
from pathlib import Path
import json
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SecureGCPContainerManager:
    def __init__(self, client_id):
        # Initialize clients
        self.cloud_run_client = run_v2.ServicesClient()
        self.artifact_client = artifactregistry_v1.ArtifactRegistryClient()
        self.docker_client = docker.from_env()

        # Security-specific initialization
        self.client_id = client_id
        self.api_key = secrets.token_urlsafe(32)
        self.jwt_secret = secrets.token_urlsafe(64)

        # Log versions for diagnostics
        self.check_dependencies()

        # Get default credentials and project
        self.credentials, self.project_id = google.auth.default()

        # Generate unique identifiers
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        random_suffix = ''.join(random.choices(
            string.ascii_lowercase + string.digits, k=4))
        self.unique_id = f"{timestamp}-{random_suffix}"

        # Set up variables with unique names
        self.region = 'us-central1'
        self.repository_name = f'secure-app-{self.client_id.split("@")[0]}'
        self.registry_location = f'{self.region}-docker.pkg.dev'
        self.image_name = 'secure-app'
        self.service_name = f'secure-app-{self.unique_id}'
        self.image_tag = f'{self.registry_location}/{self.project_id}/{
            self.repository_name}/{self.image_name}:{self.unique_id}'

    def check_dependencies(self):
        """Log dependency versions using importlib.metadata"""
        deps = ['google-cloud-run',
                'google-cloud-artifact-registry', 'docker', 'PyJWT']
        for dep in deps:
            try:
                ver = pkg_version(dep)
                logger.info(f"{dep} version: {ver}")
            except Exception as e:
                logger.warning(f"Could not get version for {dep}: {e}")

    def create_app_files(self):
        """Create necessary application files with security middleware"""
        app_dir = Path(f'secure-app-{self.unique_id}')
        app_dir.mkdir(exist_ok=True)

        # Write Flask application
        app_content = """
from flask import Flask, request, jsonify
import jwt
from functools import wraps
import os

app = Flask(__name__)

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'Missing token'}), 401
            
        try:
            if not token.startswith('Bearer '):
                raise jwt.InvalidTokenError
                
            token = token.split(' ')[1]
            payload = jwt.decode(
                token, 
                os.environ['JWT_SECRET'],
                algorithms=['HS256']
            )
            
            if payload['client_id'] != os.environ['CLIENT_ID']:
                raise jwt.InvalidTokenError
                
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
            
        return f(*args, **kwargs)
    return decorated

@app.route('/')
@require_auth
def hello():
    return jsonify({
        'message': 'Hello, World!',
        'client_id': os.environ['CLIENT_ID']
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
"""

        (app_dir / 'app.py').write_text(app_content)

        # Write requirements.txt
        requirements_content = """flask==2.0.1
werkzeug==2.0.3
pyjwt==2.3.0
gunicorn==20.1.0"""
        (app_dir / 'requirements.txt').write_text(requirements_content)

        # Write Dockerfile
        dockerfile_content = """FROM python:3.9-slim

    # Create non-root user
    RUN groupadd -r appuser && useradd -r -g appuser appuser

    # Set working directory
    WORKDIR /app

    # Copy requirements first for better caching
    COPY requirements.txt .
    RUN pip install --no-cache-dir -r requirements.txt

    # Copy application code
    COPY app.py .

    # Set ownership to non-root user
    RUN chown -R appuser:appuser /app

    # Switch to non-root user
    USER appuser

    # Expose port
    EXPOSE 8080

    # Use gunicorn for production
    CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "3", "--access-logfile", "-", "app:app"]"""
        (app_dir / 'Dockerfile').write_text(dockerfile_content)

        return app_dir

    def build_container(self, app_dir):
        """Build container using Docker SDK with security best practices"""
        try:
            logger.info("Building secure container image...")
            self.docker_client.images.build(
                path=str(app_dir),
                tag=self.image_tag,
                rm=True,
                buildargs={
                    'DOCKER_BUILDKIT': '1'
                }
            )
            logger.info("Secure container build completed")
        except docker.errors.BuildError as e:
            logger.error(f"Failed to build container: {e}")
            raise

    def create_artifact_repository(self):
        """Create secure Artifact Registry repository if it doesn't exist"""
        try:
            logger.info(
                f"Creating/checking Artifact Registry repository: {self.repository_name}")

            # Format the repository path
            parent = f"projects/{self.project_id}/locations/{self.region}"
            repository_path = f"{parent}/repositories/{self.repository_name}"

            try:
                # Try to get the repository first
                get_request = artifactregistry_v1.GetRepositoryRequest(
                    name=repository_path
                )
                existing_repo = self.artifact_client.get_repository(
                    request=get_request)
                logger.info("Repository already exists")
                return existing_repo

            except google.api_core.exceptions.NotFound:
                logger.info("Repository not found, creating new one...")

                # Repository doesn't exist, create it
                repository = artifactregistry_v1.Repository()
                repository.format_ = artifactregistry_v1.Repository.Format.DOCKER
                repository.description = f"Docker repository for {
                    self.client_id}"

                create_request = artifactregistry_v1.CreateRepositoryRequest(
                    parent=parent,
                    repository_id=self.repository_name,
                    repository=repository
                )

                operation = self.artifact_client.create_repository(
                    request=create_request)
                result = operation.result()  # Wait for operation to complete
                logger.info("Repository created successfully")

                # Configure Docker authentication
                auth_result = subprocess.run([
                    'gcloud', 'auth', 'configure-docker',
                    f'{self.region}-docker.pkg.dev'
                ], capture_output=True, text=True)

                if auth_result.returncode != 0:
                    logger.error(f"Docker authentication failed: {
                                 auth_result.stderr}")
                    raise Exception(
                        "Failed to configure Docker authentication")

                return result

        except google.api_core.exceptions.PermissionDenied as e:
            logger.error(f"Permission denied while accessing repository: {e}")
            raise
        except google.api_core.exceptions.InvalidArgument as e:
            logger.error(f"Invalid argument when creating repository: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to create repository: {e}")
            raise

    def push_to_artifact_registry(self):
        """Push container to Artifact Registry securely"""
        try:
            logger.info("Pushing container to Artifact Registry...")

            # Configure Docker credentials
            subprocess.run([
                'gcloud', 'auth', 'configure-docker',
                self.registry_location,
                '--quiet'
            ], check=True)

            # Push the image
            result = self.docker_client.images.push(self.image_tag)
            logger.info("Container pushed successfully")

            # Verify the image exists with retries
            retry_count = 0
            while retry_count < 3:
                if self.verify_image_exists():
                    return
                logger.info(
                    f"Waiting for image to be available (attempt {retry_count + 1}/3)")
                time.sleep(10)
                retry_count += 1

            raise Exception("Image not available after retries")

        except Exception as e:
            logger.error(f"Failed to push container: {e}")
            raise

    def verify_image_exists(self):
        """Verify image exists in Artifact Registry"""
        try:
            result = subprocess.run([
                'gcloud', 'artifacts', 'docker', 'images', 'list',
                f'{self.registry_location}/{self.project_id}/{self.repository_name}',
                f'--filter=tags:{self.unique_id}',
                '--format=json',
                '--quiet'
            ], capture_output=True, text=True)

            return result.returncode == 0 and bool(result.stdout.strip())

        except Exception as e:
            logger.error(f"Image verification failed: {e}")
            return False

    def deploy_to_cloud_run(self):
        """Deploy container to Cloud Run with security configurations"""
        try:
            logger.info(f"Deploying secure service to Cloud Run: {
                        self.service_name}")

            service = run_v2.Service()
            service.template = run_v2.RevisionTemplate()

            # Configure container
            container = run_v2.Container()
            container.image = self.image_tag
            container.ports = [run_v2.ContainerPort(container_port=8080)]

            # Add security-related environment variables
            container.env = [
                run_v2.EnvVar(name="CLIENT_ID", value=self.client_id),
                run_v2.EnvVar(name="API_KEY", value=self.api_key),
                run_v2.EnvVar(name="JWT_SECRET", value=self.jwt_secret)
            ]

            # Set resource limits
            container.resources = run_v2.ResourceRequirements(
                limits={
                    "cpu": "1",
                    "memory": "512Mi"
                }
            )

            service.template.containers = [container]

            # Set VPC configuration properly
            vpc_access = run_v2.VpcAccess()
            vpc_access.connector = f"projects/{self.project_id}/locations/{
                self.region}/connectors/default-connector"
            vpc_access.egress = run_v2.VpcAccess.VpcEgress.PRIVATE_RANGES_ONLY
            service.template.vpc_access = vpc_access

            # Create the service request
            request = run_v2.CreateServiceRequest(
                parent=f"projects/{self.project_id}/locations/{self.region}",
                service_id=self.service_name,
                service=service,
            )

            operation = self.cloud_run_client.create_service(request=request)
            result = operation.result()

            # Set IAM policy
            self.set_service_iam_policy()

            logger.info(f"Secure service deployed successfully: {result.uri}")
            return result

        except Exception as e:
            logger.error(f"Failed to deploy secure service: {e}")
            raise

    def set_service_iam_policy(self):
        try:
            service_name = f"projects/{self.project_id}/locations/{
                self.region}/services/{self.service_name}"

            # Allow public access for RPC endpoints
            binding = policy_pb2.Binding(
                role="roles/run.invoker",
                members=["allUsers"]  # Public RPC access
            )

            policy = policy_pb2.Policy(bindings=[binding])
            request = iam_policy_pb2.SetIamPolicyRequest(
                resource=service_name,
                policy=policy
            )

            self.cloud_run_client.set_iam_policy(request)
            logger.info(f"IAM policy set successfully for {self.service_name}")

        except Exception as e:
            logger.error(f"Failed to set IAM policy: {e}")
            raise

    def generate_access_token(self, expiration_minutes=60):
        """Generate JWT access token for client"""
        payload = {
            'client_id': self.client_id,
            'exp': datetime.now(timezone.utc) + timedelta(minutes=expiration_minutes),
            'iat': datetime.now(timezone.utc),
            'jti': secrets.token_hex(16)
        }
        return jwt.encode(payload, self.jwt_secret, algorithm='HS256')

    def get_service_info(self):
        try:
            request = run_v2.GetServiceRequest(
                name=f"projects/{self.project_id}/locations/{
                    self.region}/services/{self.service_name}"
            )

            service = self.cloud_run_client.get_service(request=request)

            # Note the double curly braces
            curl_example = f'curl -X POST {
                service.uri}/ -H "Content-Type: application/json" -d \'{{"method": "server_info"}}\''

            return {
                'service_name': self.service_name,
                'rpc_endpoint': f"{service.uri}/",
                'ws_endpoint': f"wss://{service.uri.split('https://')[1]}/ws",
                'status': service.latest_ready_revision,
                'connection_examples': {
                    'curl': curl_example,
                    'python': f'''
    import requests
    response = requests.post("{service.uri}/",
        json={{"method": "server_info"}})  # Note the double curly braces
    print(response.json())
    ''',
                    'websocket': f'''
    import websockets
    async with websockets.connect("{service.uri}/ws") as ws:
        # Note the double curly braces
        await ws.send({{"command": "subscribe", "streams": ["ledger"]}})
    '''
                }
            }

        except Exception as e:
            logger.error(f"Failed to retrieve service info: {e}")
            raise


def main():
    try:
        # Initialize with a client ID (replace with actual client ID)
        client_id = "example@domain.com"
        manager = SecureGCPContainerManager(client_id)

        logger.info(f"Starting secure deployment for client: {client_id}")

        # Create and deploy the secure service
        app_dir = manager.create_app_files()
        manager.build_container(app_dir)
        manager.create_artifact_repository()
        manager.push_to_artifact_registry()
        result = manager.deploy_to_cloud_run()

        # Get service information
        service_info = manager.get_service_info()
        logger.info(f"Service Information: {service_info}")

        # Generate initial access token
        access_token = manager.generate_access_token()
        logger.info("Initial access token generated")

        deployment_info = {
            **service_info,
            'access_token': access_token,
            'deployment_time': datetime.now(timezone.utc).isoformat()
        }

        return deployment_info

    except Exception as e:
        logger.error(f"Secure deployment workflow failed: {e}")
        raise


if __name__ == "__main__":
    try:
        deployment_info = main()

        # Generate timestamp for filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'deployment_config_{timestamp}.json'

        # Write deployment info to file
        with open(filename, 'w') as f:
            json.dump(deployment_info, f, indent=4)

        print(f"Deployment successful! Configuration saved to: {filename}")
        print("\nConnection information:")
        print(json.dumps(deployment_info, indent=4))

    except Exception as e:
        print(f"Error during deployment: {e}")
        sys.exit(1)
