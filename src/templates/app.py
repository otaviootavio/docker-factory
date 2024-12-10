from flask import Flask, request, jsonify
import jwt
from functools import wraps
import os
import logging
import sys
from datetime import datetime
import requests
from flasgger import Swagger

# Configure logging
logging.basicConfig(
    stream=sys.stdout,  # Log to stdout for Cloud Run
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('secure-app')

app = Flask(__name__)

# Configure Swagger with JWT support
app.config['SWAGGER'] = {
    'title': 'Secure Rippled API',
    'uiversion': 3
}
swagger = Swagger(app, template={
    "swagger": "2.0",
    "info": {
        "title": "Secure Rippled API",
        "description": "API documentation for a secure application with JWT authentication",
        "version": "1.0.0"
    },
    "securityDefinitions": {
        "Bearer": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
            "description": "JWT Authorization header using the Bearer scheme. Example: 'Bearer {token}'"
        }
    },
    "security": [
        {"Bearer": []}
    ]
})


# Rippled node connection URL
RIPPLED_URL = "http://localhost:5005"

def query_rippled(method, params=None):
    """Helper function to query the rippled node."""
    try:
        payload = {
            "method": method,
            "params": [params] if params else []
        }
        response = requests.post(
            RIPPLED_URL, 
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=5
        )
        if response.status_code != 200:
            logger.error(f"Rippled returned status {response.status_code}")
            return {"error": f"Rippled error: {response.status_code}"}
        return response.json()
    except requests.exceptions.ConnectionError:
        logger.error("Failed to connect to rippled")
        return {"error": "Rippled connection failed"}
    except Exception as e:
        logger.error(f"Error querying rippled: {str(e)}")
        return {"error": str(e)}

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        """
        Decorator to require authentication using JWT.
        """
        token = request.headers.get('Authorization')
        if not token:
            logger.warning("No Authorization header present")
            return jsonify({'error': 'Missing token'}), 401
            
        try:
            if not token.startswith('Bearer '):
                logger.warning("Token doesn't start with Bearer")
                raise jwt.InvalidTokenError
                
            token = token.split(' ')[1]
            jwt_secret = os.environ.get('JWT_SECRET')
            if not jwt_secret:
                logger.error("JWT_SECRET not set in environment")
                return jsonify({'error': 'Configuration error'}), 500
                
            payload = jwt.decode(
                token, 
                jwt_secret,
                algorithms=['HS256']
            )
            logger.info(f"Token decoded successfully for client: {payload.get('client_id')}")
            
            expected_client_id = os.environ.get('CLIENT_ID')
            if not expected_client_id:
                logger.error("CLIENT_ID not set in environment")
                return jsonify({'error': 'Configuration error'}), 500
                
            if payload['client_id'] != expected_client_id:
                logger.warning(f"Client ID mismatch: expected {expected_client_id}, got {payload['client_id']}")
                raise jwt.InvalidTokenError
                
        except jwt.ExpiredSignatureError:
            logger.error("Token expired")
            return jsonify({'error': 'Token expired'}), 401
        except jwt.InvalidTokenError as e:
            logger.error(f"Invalid token: {str(e)}")
            return jsonify({'error': 'Invalid token'}), 401
        except Exception as e:
            logger.error(f"Unexpected error in auth: {str(e)}")
            return jsonify({'error': 'Authentication error'}), 401
            
        return f(*args, **kwargs)
    return decorated

@app.route('/health')
def health():
    """
    Health check endpoint.
    ---
    responses:
      200:
        description: Application health status
    """
    try:
        rippled_status = query_rippled("server_info")
        node_status = "healthy" if "result" in rippled_status else "rippled not responding"
        return jsonify({
            'status': 'healthy',
            'rippled_status': node_status,
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        logger.error(f"Health check error: {str(e)}")
        return jsonify({
            'status': 'healthy',
            'rippled_status': 'error',
            'timestamp': datetime.utcnow().isoformat()
        })

@app.route('/')
@require_auth
def hello():
    """
    Main endpoint.
    ---
    responses:
      200:
        description: Main API endpoint with authentication
    """
    client_id = os.environ.get('CLIENT_ID', 'unknown')
    logger.info(f"Successful request for client: {client_id}")
    server_info = query_rippled("server_info")
    return jsonify({
        'client_id': client_id,
        'timestamp': datetime.utcnow().isoformat(),
        'node_info': server_info.get('result', {}).get('info', {})
    })

@app.route('/node/info')
@require_auth
def node_info():
    """
    Get detailed node information.
    ---
    responses:
      200:
        description: Rippled server information
    """
    return jsonify(query_rippled("server_info"))

@app.route('/node/state')
@require_auth
def node_state():
    """
    Get node state information.
    ---
    responses:
      200:
        description: Rippled server state
    """
    server_state = query_rippled("server_state")
    return jsonify(server_state)

@app.route('/validators')
@require_auth
def validators():
    """
    Get validators information.
    ---
    responses:
      200:
        description: Validator information
    """
    validators_info = query_rippled("validators")
    return jsonify(validators_info)

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
