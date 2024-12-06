import os
from pathlib import Path
from string import Template

class TemplateManager:
    def __init__(self):
        self.template_dir = Path(__file__).parent

    def load_template(self, template_name: str) -> Template:
        """Load a template file and return a Template object."""
        template_path = self.template_dir / template_name
        if not template_path.exists():
            raise FileNotFoundError(f"Template {template_name} not found")
        
        with open(template_path, 'r') as f:
            return Template(f.read())

    def render_template(self, template_name: str, **kwargs) -> str:
        """Render a template with the given kwargs."""
        template = self.load_template(template_name)
        return template.safe_substitute(**kwargs)

    def write_template(self, template_name: str, output_path: Path, **kwargs):
        """Render a template and write it to the specified path."""
        content = self.render_template(template_name, **kwargs)
        output_path.write_text(content)
