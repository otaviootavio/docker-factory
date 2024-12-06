from google.cloud import run_v2
from google.cloud import artifactregistry_v1
import google.auth

class GCPClient:
    def __init__(self):
        self.cloud_run_client = run_v2.ServicesClient()
        self.artifact_client = artifactregistry_v1.ArtifactRegistryClient()
        self.credentials, self.project_id = google.auth.default()

    @property
    def project_id(self):
        return self._project_id

    @project_id.setter
    def project_id(self, value):
        self._project_id = value
