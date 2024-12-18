#!/bin/bash

# Start Docker daemon directly with specific settings

# Start your application
exec uvicorn main:app --host 0.0.0.0 --port 8000