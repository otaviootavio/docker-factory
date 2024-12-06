import docker
import logging

logger = logging.getLogger(__name__)

class DockerClient:
    def __init__(self):
        self.client = docker.from_env()

    def build_image(self, path, tag, **kwargs):
        try:
            logger.info(f"Building Docker image: {tag}")
            self.client.images.build(
                path=str(path),
                tag=tag,
                rm=True,
                buildargs={'DOCKER_BUILDKIT': '1'},
                **kwargs
            )
            logger.info("Docker image build completed")
        except docker.errors.BuildError as e:
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
