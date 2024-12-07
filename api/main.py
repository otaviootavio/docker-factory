from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from datetime import datetime
import os
from .routes.deployments import router as deployment_router  # Updated import path
from src import db
import time
import logging
from typing import Callable
import secrets

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="Secure Deployment API",
    description="API for secure container deployments",
    version="1.0.0"
)

# Security configurations
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    API_KEY = secrets.token_urlsafe(32)
    logger.warning(f"API_KEY not found in environment variables. Generated new key: {API_KEY}")

# Rate limiting configuration
RATE_LIMIT_SECONDS = 60
MAX_REQUESTS = 100
request_history = {}

# Add CORS middleware with development settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins in development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def check_rate_limit(client_ip: str) -> bool:
    current_time = time.time()
    
    # Clean up old entries
    request_history[client_ip] = [
        timestamp for timestamp in request_history.get(client_ip, [])
        if current_time - timestamp < RATE_LIMIT_SECONDS
    ]
    
    # Check rate limit
    if len(request_history.get(client_ip, [])) >= MAX_REQUESTS:
        return False
    
    # Add new request timestamp
    request_history.setdefault(client_ip, []).append(current_time)
    return True

async def verify_api_key(api_key: str = Depends(api_key_header)):
    if api_key != API_KEY:
        logger.warning(f"Invalid API key attempt")
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )
    return api_key

@app.middleware("http")
async def security_middleware(request: Request, call_next: Callable):
    start_time = time.time()
    client_ip = request.client.host
    
    try:
        # Rate limiting check
        if not check_rate_limit(client_ip):
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please try again later."
            )
        
        # Add security headers
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Log request details
        process_time = time.time() - start_time
        logger.info(
            f"Method: {request.method} Path: {request.url.path} "
            f"Client: {client_ip} Status: {response.status_code} "
            f"Process Time: {process_time:.3f}s"
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error processing request from {client_ip}: {str(e)}")
        raise

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "timestamp": str(datetime.now()),
        "version": "1.0.0"
    }

# Secure the deployment router with API key
app.include_router(
    deployment_router,
    prefix="/deployments",
    tags=["deployments"],
    dependencies=[Depends(verify_api_key)]
)

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception: {str(exc)}")
    return {
        "status": "error",
        "message": "An internal server error occurred",
        "path": str(request.url)
    }