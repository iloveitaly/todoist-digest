"""Test todoist-digest."""

import todoist_digest
from todoist_digest import (
    object_to_dict,
    strip_markdown_links,
    todoist_project_link,
    todoist_task_link,
)


def test_import() -> None:
    """Test that the package can be imported."""
    assert isinstance(todoist_digest.__name__, str)


def test_version() -> None:
    """Test that the version is available."""
    assert isinstance(todoist_digest.__version__, str)


def test_strip_markdown_links() -> None:
    """Test stripping markdown links while preserving text."""
    content = "Check [this task](https://todoist.com) out!"
    assert strip_markdown_links(content) == "Check this task out!"


def test_todoist_task_link() -> None:
    """Test generation of todoist task links."""
    assert todoist_task_link("12345") == "https://todoist.com/app/task/12345"


def test_todoist_project_link() -> None:
    """Test generation of todoist project links."""
    assert todoist_project_link("67890") == "https://todoist.com/app/project/67890"


def test_object_to_dict() -> None:
    """Test object_to_dict helper."""

    class Dummy:
        def __init__(self):
            self.foo = "bar"

    assert object_to_dict(Dummy()) == {"foo": "bar"}


def test_render_template() -> None:
    """Test render_template functionality."""
    from todoist_digest.templates import render_template
    from todoist_digest.util import TEMPLATES_DIRECTORY

    result = render_template(
        TEMPLATES_DIRECTORY / "task.jinja",
        {"task": {"task_content": "Foo", "task_link": "https://example.com"}},
    )
    assert result.strip() == "### [Foo](https://example.com)"
