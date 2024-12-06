# GCP Container Manager

## Prerequisites

### 1. Install Python

- Python 3.8 to 3.12 required
- Virtual environment recommended

### 2. Install Google Cloud CLI (gcloud)

**For Linux (Manual Installation):**

```bash
# Download the archive
curl -O https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-cli-linux-x86_64.tar.gz

# Extract the archive (preferably in your home directory)
tar -xf google-cloud-cli-linux-x86_64.tar.gz

# Run the installation script
./google-cloud-sdk/install.sh

# Initialize gcloud
./google-cloud-sdk/bin/gcloud init
```

**For Debian/Ubuntu (Package Manager):**

```bash
# Add the Cloud SDK distribution URI as a package source
curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg

echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | sudo tee -a /etc/apt/sources.list.d/google-cloud-sdk.list

# Update and install the Cloud SDK
sudo apt-get update
sudo apt-get install google-cloud-cli
```

**Verify Installation:**

```bash
gcloud --version
```

### 3. Configure Google Cloud

```bash
# Login to Google Cloud
gcloud auth login

# List the projects
gcloud projects list

# Set your project ID
gcloud config set project YOUR_PROJECT_ID

# Enable required APIs
gcloud services enable run.googleapis.com
gcloud services enable artifactregistry.googleapis.com

# Configure Docker authentication
gcloud auth configure-docker us-central1-docker.pkg.dev

# Set up application default credentials
gcloud auth application-default login
```

## Project Setup

1. **Create Virtual Environment**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install Dependencies**
   ```bash
   pip install google-cloud-run
   pip install google-cloud-artifact-registry
   pip install docker
   pip install setuptools
   ```

## Run the Application

```bash
python main.py
```

## Service Deployment & Monitoring Tools

### Workflow:

Deploy your service:

```python3
python3 main.py
```

This will create a deployment configuration file named: deployment_config_YYYYMMDD_HHMMSS.json

The generated file contains your service details and access tokens:

```json
{
   "uri": "https://secure-app-xxxxx-xxxxx.a.run.app",
   "access_token": "eyJhbGc...",
   ...
}
```

3. You can ping your service using the generated config:

```bash
   python3 ping.py --config deployment_config_YYYYMMDD_HHMMSS.json
```

4. Alternative ping methods:

Direct URI and token:

```bash
   python3 ping.py --uri https://your-service-url --token your-access-token
```

Using environment variables:

```bash
 export SERVICE_URI="https://your-service-url"
 export SERVICE_TOKEN="your-token"
 python3 ping.py
```

Output format:

```json
{
   "timestamp": "2024-12-05T21:45:23.456789",
   "status_code": 200,
   "response_time_ms": 123,
   "data": {
   "message": "Hello, World!",
   "client_id": "example@domain.com"
}
```

## Troubleshooting

### Common gcloud Installation Issues:

1. **Python Version Issues**

   - Check Python version: `python --version`
   - The CLI requires Python 3.8 to 3.12

2. **Permission Issues**

   ```bash
   # If permission denied during installation
   sudo chown -R $USER google-cloud-sdk/
   ```

3. **Path Issues**

   ```bash
   # Add to ~/.bashrc or ~/.zshrc
   export PATH=$PATH:/path/to/google-cloud-sdk/bin
   ```

4. **Proxy Settings**
   - If behind a proxy, see: https://cloud.google.com/sdk/docs/proxy-settings

### Other Common Issues:

1. **Docker Authentication Issues**

   ```bash
   gcloud auth configure-docker us-central1-docker.pkg.dev
   ```

2. **API Access Issues**
   ```bash
   # Grant necessary roles
   gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
       --member="user:your-email@example.com" \
       --role="roles/run.admin"
   ```

## Support

- [Google Cloud CLI Documentation](https://cloud.google.com/sdk/docs)
- [Cloud Run Documentation](https://cloud.google.com/run/docs)
