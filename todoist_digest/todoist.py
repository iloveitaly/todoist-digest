"""
Todoist API extensions, mostly around the sync API, that won't be added to the core API (I tried)
"""

from datetime import datetime
from functools import lru_cache

import requests
from todoist_api_python.models import Task

from .util import log


# https://github.com/iloveitaly/todoist-api-python/commit/ec83531fae94a2ccd0a4bd6b2d1db95d86b129b6
def todoist_get_sync_resource(api, resource_type):
    """
    >>> todoist_get_sync_resource(api, "collaborators")
    """

    from todoist_api_python._core.endpoints import get_api_url
    from todoist_api_python._core.http_requests import post

    endpoint = get_api_url("sync")
    data = {
        "resource_types": [resource_type],
        "sync_token": "*",
    }
    resource_data = post(api._session, endpoint, api._token, data=data)
    return resource_data


# https://developer.todoist.com/sync/v9#get-item-info
# https://github.com/iloveitaly/todoist-api-python/commit/ec83531fae94a2ccd0a4bd6b2d1db95d86b129b6
@lru_cache(maxsize=None)
def todoist_get_item_info(api, item_id):
    from todoist_api_python._core.endpoints import get_api_url
    from todoist_api_python._core.http_requests import get

    endpoint = get_api_url("items/get")
    data = {
        "item_id": item_id,
    }
    resource_data = get(api._session, endpoint, api._token, params=data)
    return resource_data


def todoist_get_completed_activity(api, task_id):
    from todoist_api_python._core.endpoints import get_api_url
    from todoist_api_python._core.http_requests import get

    endpoint = get_api_url("activities")
    data = {
        "limit": 100,
        "event_type": "completed",
        "object_id": task_id,
        "object_type": "item",
    }
    resource_data = get(api._session, endpoint, api._token, params=data)
    return resource_data


def todoist_uncomplete_tasks_with_post_completion_comments(
    api,
    *,
    completed_tasks: list[Task],
    comments_by_task_id: dict,
) -> set[str]:
    """Uncomplete tasks when a comment is posted after task completion.

    This uses the Todoist API v1 SDK method `api.uncomplete_task(task_id)`.

    Notes:
    - Skips recurring tasks and logs a warning.
    - Uses the latest completion time when a task appears multiple times in
      the completed feed (e.g., complete→uncomplete→complete cycles).
    - Returns a set of task IDs (as strings) that were uncompleted.
    """

    log.info("inspecting if tasks should be uncompleted")

    if not comments_by_task_id:
        return set()

    # Latest comment per task (any commenter). The caller is expected to pre-filter
    # comments by time window (e.g., posted_at > last_synced).
    latest_comment_by_task_id: dict[str, datetime] = {}
    for task_id, task_comments in comments_by_task_id.items():
        if not task_comments:
            continue
        latest_comment_by_task_id[str(task_id)] = max(
            task_comments, key=lambda c: c["posted_at"]
        )["posted_at"]

    # Latest completion per task within completed feed.
    completed_by_task_id: dict[str, Task] = {}
    for task in completed_tasks:
        completed_at = task.completed_at

        # I don't expect this to occur
        if completed_at is None:
            log.warning(
                "completed task missing completed_at",
                task_id=str(task.id),
            )
            continue

        # The completed feed can include duplicate task IDs if a task was completed,
        # reopened, and completed again within the time window, so we keep the latest.
        task_id = str(task.id)
        current = completed_by_task_id.get(task_id)
        if (
            current is None
            or current.completed_at is None
            or completed_at > current.completed_at
        ):
            completed_by_task_id[task_id] = task

    uncompleted_task_ids: set[str] = set()
    for task_id, completed_task in completed_by_task_id.items():
        latest_comment_at = latest_comment_by_task_id.get(task_id)
        if latest_comment_at is None:
            continue

        completed_at = completed_task.completed_at
        if completed_at is None or latest_comment_at <= completed_at:
            continue

        due = completed_task.due
        is_recurring = bool(due.is_recurring) if due else False
        if is_recurring:
            log.warning(
                "Skipping uncomplete for recurring task",
                task_id=task_id,
                completed_at=completed_at,
                latest_comment_at=latest_comment_at,
            )
            continue

        try:
            api.uncomplete_task(task_id)
            uncompleted_task_ids.add(task_id)
            log.info(
                "Uncompleted task due to comment after completion",
                task_id=task_id,
                completed_at=completed_at,
                latest_comment_at=latest_comment_at,
            )
        except requests.exceptions.HTTPError as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            log.warning(
                "Failed to uncomplete task",
                task_id=task_id,
                completed_at=completed_at,
                latest_comment_at=latest_comment_at,
                status_code=status_code,
            )

    return uncompleted_task_ids
