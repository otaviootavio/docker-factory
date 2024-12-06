import json
import sys
from datetime import datetime
from src.container_manager import SecureGCPContainerManager
from src.utils.logging import setup_logging

logger = setup_logging(__name__)


def main():
    try:
        # Initialize with a client ID (replace with actual client ID)
        client_id = "example@domain.com"
        manager = SecureGCPContainerManager(client_id)

        # Execute deployment
        deployment_info = manager.deploy()

        # Generate timestamp for filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"deployment_config_{timestamp}.json"

        # Write deployment info to file
        with open(filename, "w") as f:
            json.dump(deployment_info, f, indent=4)

        print(f"Deployment successful! Configuration saved to: {filename}")
        print("\nConnection information:")
        print(json.dumps(deployment_info, indent=4))

        return deployment_info

    except Exception as e:
        logger.error(f"Deployment failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
