import logging
from google.cloud import run_v2
from google.iam.v1 import iam_policy_pb2, policy_pb2

logger = logging.getLogger(__name__)


class CloudRunService:
    def __init__(self, gcp_client):
        self.gcp_client = gcp_client

    def deploy(self, service_name, image_tag, region, env_vars):
        try:
            """Deploy container to Cloud Run with security configurations"""
            logger.info(f"Deploying secure service to Cloud Run: {
                        service_name}")

            service = run_v2.Service()
            service.template = run_v2.RevisionTemplate()

            # Configure container
            container = run_v2.Container()
            container.image = image_tag
            container.ports = [run_v2.ContainerPort(container_port=8080)]

            # Add environment variables with logging
            container.env = []
            for key, value in env_vars.items():
                logger.info(f"Setting environment variable: {key}")
                container.env.append(run_v2.EnvVar(name=key, value=value))

            # Verify environment variables
            if not any(env.name == 'JWT_SECRET' for env in container.env):
                raise ValueError("JWT_SECRET environment variable not set")
            if not any(env.name == 'CLIENT_ID' for env in container.env):
                raise ValueError("CLIENT_ID environment variable not set")

            # Set resource limits
            container.resources = run_v2.ResourceRequirements(
                limits={
                    "cpu": "1",
                    "memory": "512Mi"
                }
            )

            service.template.containers = [container]

            # Set VPC configuration
            vpc_access = run_v2.VpcAccess()
            vpc_access.connector = f"projects/{self.gcp_client.project_id}/locations/{
                region}/connectors/default-connector"
            vpc_access.egress = run_v2.VpcAccess.VpcEgress.PRIVATE_RANGES_ONLY
            service.template.vpc_access = vpc_access

            # Create the service
            request = run_v2.CreateServiceRequest(
                parent=f"projects/{self.gcp_client.project_id}/locations/{region}",
                service_id=service_name,
                service=service,
            )

            operation = self.gcp_client.cloud_run_client.create_service(
                request=request)
            result = operation.result()

            # Set IAM policy
            self._set_service_iam_policy(service_name, region)

            logger.info(f"Secure service deployed successfully: {result.uri}")
            return result

        except Exception as e:
            logger.error(f"Failed to deploy secure service: {e}")
            raise

    def get_service_info(self, service_name, region):
        try:
            request = run_v2.GetServiceRequest(
                name=f"projects/{self.gcp_client.project_id}/locations/{
                    region}/services/{service_name}"
            )

            service = self.gcp_client.cloud_run_client.get_service(
                request=request)

            return {
                'service_name': service_name,
                'rpc_endpoint': f"{service.uri}/",
                'ws_endpoint': f"wss://{service.uri.split('https://')[1]}/ws",
                'status': service.latest_ready_revision,
                'connection_examples': self._generate_connection_examples(service.uri)
            }

        except Exception as e:
            logger.error(f"Failed to retrieve service info: {e}")
            raise

    def _set_service_iam_policy(self, service_name, region):
        try:
            service_path = f"projects/{self.gcp_client.project_id}/locations/{
                region}/services/{service_name}"

            binding = policy_pb2.Binding(
                role="roles/run.invoker",
                members=["allUsers"]
            )

            policy = policy_pb2.Policy(bindings=[binding])
            request = iam_policy_pb2.SetIamPolicyRequest(
                resource=service_path,
                policy=policy
            )

            self.gcp_client.cloud_run_client.set_iam_policy(request)
            logger.info(f"IAM policy set successfully for {service_name}")

        except Exception as e:
            logger.error(f"Failed to set IAM policy: {e}")
            raise

    def _generate_connection_examples(self, uri):
        return {
            'curl': f'curl -X POST {uri}/ -H "Content-Type: application/json" -d \'{{"method": "server_info"}}\'',
            'python': f'''
import requests
response = requests.post("{uri}/",
    json={{"method": "server_info"}})
print(response.json())
''',
            'websocket': f'''
import websockets
async with websockets.connect("{uri}/ws") as ws:
    await ws.send({{"command": "subscribe", "streams": ["ledger"]}})
'''
        }
