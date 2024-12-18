import docker
import logging

logger = logging.getLogger(__name__)


class DockerClient:
    def __init__(self):
        self.client = docker.from_env()

    def build_image(self, path, tag):
        try:
            logger.info(f"Building Docker image: {tag}")
            self.client.images.build(path=str(path), tag=tag, rm=True)
            logger.info("Docker image build completed")
        except Exception as e:
            logger.error(f"Failed to build Docker image: {e}")
            raise

    def push_image(self, tag):
        try:
            logger.info(f"Pushing Docker image: {tag}")
            result = self.client.images.push(tag)
            logger.info("Docker image pushed successfully")
            return result
        except Exception as e:
            logger.error(f"Failed to push Docker image: {e}")
            raise
    
    """Aggressively clean Docker build cache and unused objects"""        
    def prune_builds(self):
        try:
            # Remove build cache
            self.client.api.prune_builds()
            
            # Remove unused containers
            self.client.containers.prune()
            
            # Remove unused images
            self.client.images.prune()
            
            # Force remove dangling images
            dangling_images = self.client.images.list(filters={'dangling': True})
            for image in dangling_images:
                try:
                    self.client.images.remove(image.id, force=True)
                except Exception:
                    pass
                    
        except Exception as e:
            logger.error(f"Error during Docker cleanup: {e}")
            raise
