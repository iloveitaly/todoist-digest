import re
import sys
from functools import lru_cache
from pathlib import Path

from decouple import config
from jinja2 import Environment, FileSystemLoader, StrictUndefined, Template

from todoist_digest.util import TEMPLATES_DIRECTORY

JINJGA_DEBUG = config("JINJA_DEBUG", default=False, cast=bool)


# TODO crazy, looks like line information is not outputted from jinja
#      https://github.com/saltstack/salt/blob/18ca4fdfa9e9c16fb10006f1221254707bece308/salt/utils/templates.py#L283


@lru_cache(maxsize=None)
def get_jinja_env(template_dir: str) -> Environment:
    # these extensions are builtin
    extensions = ["jinja2.ext.do", "jinja2.ext.loopcontrols"]

    if JINJGA_DEBUG:
        extensions.append("jinja2.ext.debug")

    return Environment(
        loader=FileSystemLoader(template_dir),
        # autoescape=True,
        # trim_blocks=True,
        # lstrip_blocks=True,
        extensions=extensions,
        # https://alexwlchan.net/2022/strict-jinja/
        undefined=StrictUndefined,
        # debug=JINJGA_DEBUG,
    )


# https://stackoverflow.com/questions/26967433/how-to-get-line-number-causing-an-exception-other-than-templatesyntaxerror-in
tb_frame_re = re.compile(
    r"<frame at 0x[a-z0-9]*, file '(.*)', line (\d+), (?:code top-level template code|code template)>"
)


# TODO this looks to be built in now?
def jinja2_render_traceback(src_path):
    traceback_print = ""
    # Get traceback objects
    typ, value, tb = sys.exc_info()
    # Iterate over nested traceback frames
    while tb:
        # Parse traceback frame string
        tb_frame_str = str(tb.tb_frame)
        tb_frame_match = tb_frame_re.match(tb_frame_str)
        tb_frame_istemplate = False
        # Identify frames corresponding to Jinja2 templates
        if tb.tb_frame.f_code.co_filename == "<template>":
            # Top-most template
            tb_src_path = src_path
            tb_lineno = tb.tb_lineno
            tb_frame_istemplate = True
        elif tb_frame_match:
            # nested child templates
            tb_src_path = tb_frame_match.group(1)
            tb_lineno = tb_frame_match.group(2)
            tb_frame_istemplate = True
        # Factorized string formatting
        if tb_frame_istemplate:
            traceback_print += f"  Template '{tb_src_path}', line {tb_lineno}\n"
            # Fetch the line raising the exception
            with open(tb_src_path, "r") as tb_src_file:
                for lineno, line in enumerate(tb_src_file):
                    if lineno == int(tb_lineno) - 1:
                        traceback_print += "    " + line.strip() + "\n"
                        break
        tb = tb.tb_next
    # Strip the final line jump
    return traceback_print[:-1]


def render_template(template_path: Path, context: dict) -> str:
    env = get_jinja_env(TEMPLATES_DIRECTORY)
    template = env.get_template(str(template_path.relative_to(TEMPLATES_DIRECTORY)))

    try:
        html_content = template.render(**context)
    except Exception as e:
        # print(jinja2_render_traceback(template_path))
        raise e

    return html_content
