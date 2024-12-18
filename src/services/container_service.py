import logging
from pathlib import Path
from ..templates import TemplateManager

logger = logging.getLogger(__name__)

class ContainerService:
    def __init__(self, docker_client):
        self.docker_client = docker_client
        self.template_manager = TemplateManager()
        # Create base data directory if it doesn't exist
        self.base_data_dir = Path("./data")
        self.base_data_dir.mkdir(exist_ok=True)

    def create_app_files(self, unique_id):
        """Create necessary application files with security middleware"""
        app_dir = self.base_data_dir / f"secure-app-{unique_id}"
        app_dir.mkdir(exist_ok=True)
        # Create files from templates
        self.template_manager.write_template("app.py", app_dir / "app.py")
        self.template_manager.write_template("requirements.txt", app_dir / "requirements.txt")
        self.template_manager.write_template("dockerfile", app_dir / "Dockerfile")
        
        self.template_manager.write_template("rippled.cfg", app_dir / "rippled.cfg")
        self.template_manager.write_template("validators.txt", app_dir / "validators.txt")
        self.template_manager.write_template("supervisord.conf", app_dir / "supervisord.conf")
        return app_dir

    def build_container(self, app_dir, image_tag):
        """Build container using Docker SDK with security best practices"""
        try:
            logger.info("Building secure container image...")
            self.docker_client.build_image(path=str(app_dir), tag=image_tag)
        except Exception as e:
            logger.error(f"Failed to build container: {e}")
            raise

    def remove_app_files(self, unique_id):
        """Remove application files and clean up the directory"""
        app_dir = self.base_data_dir / f"secure-app-{unique_id}"
        try:
            if app_dir.exists() and app_dir.is_dir():
                for file in app_dir.iterdir():
                    file.unlink()  # Remove each file
                app_dir.rmdir()  # Remove the directory itself
                logger.info(f"Application files for {unique_id} removed successfully.")
            else:
                logger.warning(f"Application directory {app_dir} does not exist or is not a directory.")
        except Exception as e:
            logger.error(f"Failed to remove application files for {unique_id}: {e}")
            raise