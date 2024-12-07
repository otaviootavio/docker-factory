FROM debian:bullseye-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    lsb-release \
    python3 \
    python3-pip \
    python3-dev \
    gcc \
    libffi-dev \
    iptables \
    && rm -rf /var/lib/apt/lists/*

# Install Docker
RUN curl -fsSL https://get.docker.com -o get-docker.sh && \
    sh get-docker.sh && \
    rm get-docker.sh

# Install Docker Compose
RUN curl -L "https://github.com/docker/compose/releases/download/v2.23.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose && \
    chmod +x /usr/local/bin/docker-compose

# Set up workspace
WORKDIR /app

# Copy and install requirements
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

RUN curl -L "https://github.com/docker/compose/releases/download/v2.23.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose && \
    chmod +x /usr/local/bin/docker-compose
# Set up workspace
WORKDIR /app
# Copy and install requirements
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt
# Copy application code
COPY . .
# Set up Google Cloud SDK
RUN curl -sSL https://sdk.cloud.google.com | bash
ENV PATH=/root/google-cloud-sdk/bin:$PATH

# Copy and configure GCP credentials
COPY permission.json /root/google-cloud-sdk/permission.json

# Configure gcloud and Docker with service account
RUN gcloud auth activate-service-account --key-file=/root/google-cloud-sdk/permission.json && \
    gcloud auth configure-docker us-central1-docker.pkg.dev

# Create necessary directories
RUN mkdir -p /root/.config/gcloud /root/.docker

# Expose port
EXPOSE 8000

# Copy start script
COPY start.sh /start.sh
RUN chmod +x /start.sh

CMD ["/start.sh"]