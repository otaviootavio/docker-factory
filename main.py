from google.cloud import container_v1
from google.cloud import artifactregistry_v1
import google.auth
from pathlib import Path
import docker
from kubernetes import client, config
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GCPContainerManager:
    def __init__(self):
        # Initialize clients
        self.container_client = container_v1.ClusterManagerClient()
        self.artifact_client = artifactregistry_v1.ArtifactRegistryClient()
        self.docker_client = docker.from_env()
        
        # Get default credentials and project
        self.credentials, self.project_id = google.auth.default()
        
        # Set up variables
        self.zone = 'us-central1-a'
        self.cluster_name = 'hello-world-cluster'
        self.registry_location = f'{self.project_id}-docker.pkg.dev'
        self.repository_name = 'hello-world'
        self.image_tag = f'{self.registry_location}/{self.project_id}/{self.repository_name}:latest'

    def create_app_files(self):
        """Create necessary application files"""
        app_dir = Path('hello-world-app')
        app_dir.mkdir(exist_ok=True)
        
        # Write Flask application
        app_content = """
from flask import Flask
app = Flask(__name__)

@app.route('/')
def hello():
    return 'Hello, World!'

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
                rm=True  # Remove intermediate containers
            )
            logger.info("Container build completed")
        except docker.errors.BuildError as e:
            logger.error(f"Failed to build container: {e}")
            raise

    def create_gke_cluster(self):
        """Create GKE cluster using Google Cloud SDK"""
        cluster_path = f'projects/{self.project_id}/locations/{self.zone}/clusters/{self.cluster_name}'
        
        cluster_config = {
            'name': self.cluster_name,
            'initial_node_count': 1,
            'node_config': {
                'machine_type': 'e2-small'
            }
        }
        
        try:
            operation = self.container_client.create_cluster(
                parent=f'projects/{self.project_id}/locations/{self.zone}',
                cluster=cluster_config
            )
            operation.result()  # Wait for cluster creation
            logger.info("Cluster created successfully")
        except Exception as e:
            logger.warning(f"Cluster creation failed (might already exist): {e}")

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

    def deploy_to_gke(self):
        """Deploy container to GKE using Kubernetes Python client"""
        try:
            # Load kube config
            import subprocess
            subprocess.run([
                'gcloud', 'container', 'clusters', 
                'get-credentials', self.cluster_name,
                '--zone', self.zone,
                '--project', self.project_id
            ], check=True)

            config.load_kube_config()
            k8s_apps_v1 = client.AppsV1Api()
            
            # Create deployment
            deployment = client.V1Deployment(
                metadata=client.V1ObjectMeta(name="hello-world"),
                spec=client.V1DeploymentSpec(
                    replicas=1,
                    selector=client.V1LabelSelector(
                        match_labels={"app": "hello-world"}
                    ),
                    template=client.V1PodTemplateSpec(
                        metadata=client.V1ObjectMeta(
                            labels={"app": "hello-world"}
                        ),
                        spec=client.V1PodSpec(
                            containers=[
                                client.V1Container(
                                    name="hello-world",
                                    image=self.image_tag,
                                    ports=[client.V1ContainerPort(container_port=8080)]
                                )
                            ]
                        )
                    )
                )
            )
            
            # Apply deployment
            k8s_apps_v1.create_namespaced_deployment(
                namespace="default",
                body=deployment
            )
            logger.info("Deployment created successfully")
        except client.rest.ApiException as e:
            logger.error(f"Failed to deploy to GKE: {e}")
            raise

    def get_container_info(self):
        """Retrieve container information using Kubernetes client"""
        try:
            k8s_core_v1 = client.CoreV1Api()
            
            # Get pod information
            pods = k8s_core_v1.list_namespaced_pod(
                namespace="default",
                label_selector="app=hello-world"
            )
            
            # Get cluster information
            cluster_path = f'projects/{self.project_id}/locations/{self.zone}/clusters/{self.cluster_name}'
            cluster_info = self.container_client.get_cluster(name=cluster_path)
            
            container_info = {
                'cluster_status': cluster_info.status,
                'endpoint': cluster_info.endpoint,
                'location': cluster_info.location,
                'pods': [{
                    'name': pod.metadata.name,
                    'status': pod.status.phase,
                    'host_ip': pod.status.host_ip
                } for pod in pods.items]
            }
            
            return container_info
            
        except (client.rest.ApiException, Exception) as e:
            logger.error(f"Failed to retrieve container info: {e}")
            raise

def main():
    try:
        manager = GCPContainerManager()
        
        # Execute workflow
        app_dir = manager.create_app_files()
        manager.build_container(app_dir)
        manager.create_gke_cluster()
        manager.push_to_artifact_registry()
        manager.deploy_to_gke()
        
        # Get and display container information
        container_info = manager.get_container_info()
        logger.info(f"Container Information: {container_info}")
        
        return container_info
        
    except Exception as e:
        logger.error(f"Workflow failed: {e}")
        raise

if __name__ == "__main__":
    main()