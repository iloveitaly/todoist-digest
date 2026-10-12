from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import create_autospec, sentinel

import pytest
from click.testing import CliRunner
from todoist_api_python.api import TodoistAPI

import todoist_digest
from todoist_digest import cli, get_completed_tasks


@pytest.mark.parametrize(
    ("pages", "expected"),
    [
        ([], []),
        ([[]], []),
        (
            [[], [sentinel.first, sentinel.second], [sentinel.third]],
            [sentinel.first, sentinel.second, sentinel.third],
        ),
    ],
)
def test_get_completed_tasks_uses_utc_window_and_flattens_pages(pages, expected):
    api = create_autospec(TodoistAPI, instance=True)
    api.get_project.return_value = SimpleNamespace(name="Sample Project")
    api.get_completed_tasks_by_completion_date.return_value = iter(pages)

    # Keep whenever real so dependency API changes cannot be hidden by mocks.
    before = datetime.now(UTC)
    result = get_completed_tasks(api, "12345")
    after = datetime.now(UTC)

    assert result == expected
    api.get_project.assert_called_once_with("12345")
    kwargs = api.get_completed_tasks_by_completion_date.call_args.kwargs
    since, until = kwargs["since"], kwargs["until"]
    assert isinstance(since, datetime)
    assert isinstance(until, datetime)
    assert since.tzinfo is UTC
    assert until.tzinfo is UTC
    assert before <= until <= after
    assert until - since == timedelta(days=30)
    api.get_completed_tasks_by_completion_date.assert_called_once_with(
        since=since, until=until, filter_query="#Sample Project", limit=200
    )


@pytest.mark.parametrize("target_project", ["Sample Project", "12345"])
def test_cli_renders_completed_task_digest(monkeypatch, target_project):
    api = create_autospec(TodoistAPI, instance=True)
    project = SimpleNamespace(id="12345", name="Sample Project")
    task = SimpleNamespace(
        id="67890",
        content="Finish [the report](https://example.com)",
        completed_at=datetime(2026, 10, 12, 12, tzinfo=UTC),
        due=None,
    )
    api.get_projects.return_value = iter([[project]])
    api.get_project.return_value = project
    api.get_completed_tasks_by_completion_date.return_value = iter([[task]])
    api.get_tasks.return_value = iter([[]])
    api.get_comments.return_value = iter([])
    api.filter_tasks.return_value = iter([[]])
    monkeypatch.setattr(todoist_digest, "get_api", lambda: api)
    monkeypatch.setattr(
        todoist_digest,
        "todoist_get_sync_resource",
        lambda *_: {"collaborators": [{"id": "user-1", "email": "user@example.com"}]},
    )
    monkeypatch.setattr(
        todoist_digest,
        "todoist_get_completed_activity",
        lambda *_: {"results": [{"initiator_id": "user-1"}]},
    )
    send_email = create_autospec(todoist_digest.send_markdown_email)
    monkeypatch.setattr(todoist_digest, "send_markdown_email", send_email)

    result = CliRunner().invoke(
        cli,
        [
            "--last-synced",
            "2026-10-11T00:00:00Z",
            "--target-user",
            "user@example.com",
            "--target-project",
            target_project,
            "--email-auth",
            "smtp://example.com",
            "--email-to",
            "recipient@example.com",
        ],
    )

    assert result.exit_code == 0, result.exception
    api.get_project.assert_called_once_with("12345")
    api.get_completed_tasks_by_completion_date.assert_called_once()
    api.uncomplete_task.assert_not_called()
    send_email.assert_called_once()
    auth, markdown, subject, recipient = send_email.call_args.args
    assert auth == "smtp://example.com"
    assert "# Project [Sample Project]" in markdown
    assert "## Completed Tasks" in markdown
    assert "[Finish the report](https://todoist.com/app/task/67890)" in markdown
    assert subject.endswith("Todoist Digest for Sample Project")
    assert recipient == "recipient@example.com"
