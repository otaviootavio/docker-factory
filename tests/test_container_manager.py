import unittest
from unittest.mock import Mock, patch
from src.container_manager import SecureGCPContainerManager


class TestSecureGCPContainerManager(unittest.TestCase):
    def setUp(self):
        self.client_id = "test@example.com"

    @patch("src.clients.gcp_client.GCPClient")
    @patch("src.clients.docker_client.DockerClient")
    def test_initialization(self, mock_docker, mock_gcp):
        manager = SecureGCPContainerManager(self.client_id)
        self.assertEqual(manager.client_id, self.client_id)
        self.assertIsNotNone(manager.unique_id)

    # Add more tests as needed


if __name__ == "__main__":
    unittest.main()
