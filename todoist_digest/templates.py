from functools import lru_cache
from pathlib import Path

from decouple import config
from jinja2 import Environment, FileSystemLoader, Template

from todoist_digest.util import TEMPLATES_DIRECTORY

JINJGA_DEBUG = config("JINJA_DEBUG", default=False, cast=bool)


@lru_cache(maxsize=None)
def get_jinja_env(template_dir: str) -> Environment:
    extensions = ["jinja2.ext.do", "jinja2.ext.loopcontrols"]

    if JINJGA_DEBUG:
        extensions.append("jinja2.ext.debug")

    return Environment(
        loader=FileSystemLoader(template_dir),
        # autoescape=True,
        # trim_blocks=True,
        # lstrip_blocks=True,
        extensions=extensions,
        # debug=JINJGA_DEBUG,
    )


def render_template(template_path: Path, context: dict) -> str:
    env = get_jinja_env(TEMPLATES_DIRECTORY)
    template = env.get_template(str(template_path.relative_to(TEMPLATES_DIRECTORY)))
    html_content = template.render(**context)
    return html_content
