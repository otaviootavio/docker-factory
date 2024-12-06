import json
import os
from google.oauth2 import service_account
from google.cloud import run_v2
from google.cloud import artifactregistry_v1


class GCPClient:
    def __init__(self):
        # Load and validate credentials
        credentials_str = os.getenv("GCP_SERVICE_ACCOUNT_KEY")
        if not credentials_str:
            raise ValueError("GCP_SERVICE_ACCOUNT_KEY environment variable not set")

        try:
            credentials_json = json.loads(credentials_str)

            # Validate required fields
            required_fields = [
                "type",
                "project_id",
                "private_key_id",
                "private_key",
                "client_email",
                "client_id",
                "auth_uri",
                "token_uri",
                "auth_provider_x509_cert_url",
                "client_x509_cert_url",
            ]

            missing_fields = [field for field in required_fields if field not in credentials_json]
            if missing_fields:
                raise ValueError(
                    f"Missing required fields in credentials: {missing_fields}")

            self._project_id = credentials_json["project_id"]

            # Create credentials object with explicit scopes
            self.credentials = service_account.Credentials.from_service_account_info(
                credentials_json,
                scopes=[
                    "https://www.googleapis.com/auth/cloud-platform",
                    "https://www.googleapis.com/auth/cloudplatformprojects",
                    "https://www.googleapis.com/auth/cloud-platform.read-only",
                ],
            )

            # Initialize clients with credentials
            self.cloud_run_client = run_v2.ServicesClient(credentials=self.credentials)
            self.artifact_client = artifactregistry_v1.ArtifactRegistryClient(credentials=self.credentials)

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in GCP_SERVICE_ACCOUNT_KEY: {str(e)}")
        except Exception as e:
            raise ValueError(f"Error initializing GCP client: {str(e)}")

    @property
    def project_id(self):
        return self._project_id
