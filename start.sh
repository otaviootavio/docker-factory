#!/bin/bash

# Start Docker daemon directly with specific settings
dockerd --host=unix:///var/run/docker.sock \
        --host=tcp://0.0.0.0:2375 \
        --tls=false \
        &

# Wait for Docker to be ready
echo "Waiting for Docker to start..."
timeout=30
while ! docker info >/dev/null 2>&1; do
    timeout=$((timeout - 1))
    if [ $timeout -eq 0 ]; then
        echo "Timeout waiting for Docker to start"
        exit 1
    fi
    echo "Waiting for Docker daemon..."
    sleep 1
done

echo "Docker daemon is ready"

# Start your application
exec uvicorn api.main:app --host 0.0.0.0 --port 8000