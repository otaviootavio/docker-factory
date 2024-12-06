import requests
import sys
import json
from typing import Dict, Optional
import argparse
from datetime import datetime


class ServicePinger:
    def __init__(self, config: Dict):
        self.uri = config['rpc_endpoint'].rstrip('/')  # Now using rpc_endpoint
        self.access_token = config['access_token']
        self.headers = {"Authorization": f"Bearer {self.access_token}"}

    def ping(self) -> Dict:
        try:
            print("Attempting to connect with:")
            print(f"URI: {self.uri}")
            print(f"Headers: {self.headers}")

            response = requests.get(
                self.uri,
                headers=self.headers,
                timeout=10
            )

            print(f"\nRequest headers sent: {response.request.headers}")
            print(f"Response headers received: {response.headers}")

            response.raise_for_status()

            return {
                'timestamp': datetime.now().isoformat(),
                'status_code': response.status_code,
                'response_time_ms': int(response.elapsed.total_seconds() * 1000),
                'data': response.json() if response.text else None
            }

        except requests.exceptions.RequestException as e:
            return {
                'timestamp': datetime.now().isoformat(),
                'error': str(e),
                'type': type(e).__name__,
                'details': {
                    'uri': self.uri,
                    'headers_sent': self.headers
                }
            }


def load_deployment_info(file_path: Optional[str] = None) -> Dict:
    """Load deployment info from file or use default"""
    if file_path:
        try:
            with open(file_path) as f:
                data = json.load(f)
                print(f"Loaded configuration: {json.dumps(data, indent=2)}")
                return data
        except Exception as e:
            print(f"Error loading config file: {e}")
            sys.exit(1)

    return {
        'uri': 'https://secure-app-20241205-211329-ibpi-6r3xxre5eq-uc.a.run.app',
        'access_token': 'your_token_here'
    }


def main():
    parser = argparse.ArgumentParser(description='Ping a deployed service')
    parser.add_argument('--config', help='Path to deployment info JSON file')
    parser.add_argument('--uri', help='Service URI')
    parser.add_argument('--token', help='Access token')
    args = parser.parse_args()

    # Load configuration
    if args.config:
        info = load_deployment_info(args.config)
    else:
        info = {
            'rpc_endpoint': args.uri,
            'access_token': args.token
        }

    # Create pinger with entire config
    pinger = ServicePinger(info)
    result = pinger.ping()

    print("\nResult:")
    print(json.dumps(result, indent=2))

    if 'error' in result:
        sys.exit(1)


if __name__ == "__main__":
    main()
