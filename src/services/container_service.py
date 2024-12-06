import logging
from pathlib import Path
from ..templates import TemplateManager

logger = logging.getLogger(__name__)

class ContainerService:
    def __init__(self, docker_client):
        self.docker_client = docker_client
        self.template_manager = TemplateManager()

    def create_app_files(self, unique_id):
        """Create necessary application files with security middleware"""
        app_dir = Path(f'secure-app-{unique_id}')
        app_dir.mkdir(exist_ok=True)
        
        # Create files from templates
        self.template_manager.write_template(
            'app.py.template',
            app_dir / 'app.py'
        )
        
        self.template_manager.write_template(
            'requirements.template',
            app_dir / 'requirements.txt'
        )
        
        self.template_manager.write_template(
            'dockerfile.template',
            app_dir / 'Dockerfile'
        )
        
        return app_dir

    def build_container(self, app_dir, image_tag):
        """Build container using Docker SDK with security best practices"""
        try:
            logger.info("Building secure container image...")
            self.docker_client.build_image(
                path=str(app_dir),
                tag=image_tag
            )
        except Exception as e:
            logger.error(f"Failed to build container: {e}")
            raise
