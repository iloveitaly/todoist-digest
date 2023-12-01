import datetime
import os
import re
from functools import lru_cache

import click
import funcy as f
import funcy_pipe as fp
from dateutil import parser
from todoist_api_python.api import TodoistAPI
from todoist_api_python.models import Collaborator


# https://github.com/Doist/todoist-api-python/issues/38
# backoff 5xx errors
def patch_todoist_api():
    import backoff
    import requests
    import todoist_api_python.http_requests

    patch_targets = ["delete", "get", "json", "post"]
    for target in patch_targets:
        original_function = getattr(todoist_api_python.http_requests, target)

        setattr(
            todoist_api_python.http_requests,
            f"original_{target}",
            original_function,
        )

        patched_function = backoff.on_exception(
            backoff.expo, requests.exceptions.HTTPError
        )(original_function)

        setattr(
            todoist_api_python.http_requests,
            target,
            patched_function,
        )


patch_todoist_api()


@lru_cache(maxsize=None)
def collaborator_map(api):
    """
    returns a map of collaborator_id -> collaborator
    """
    result = todoist_get_sync_resource(api, "collaborators")
    collaborators = result["collaborators"]

    return {collaborator["id"]: collaborator for collaborator in collaborators}


# https://github.com/iloveitaly/todoist-api-python/commit/ec83531fae94a2ccd0a4bd6b2d1db95d86b129b6
def todoist_get_sync_resource(api, resource_type):
    from todoist_api_python.endpoints import get_sync_url
    from todoist_api_python.http_requests import post

    endpoint = get_sync_url("sync")
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
    from todoist_api_python.endpoints import get_sync_url
    from todoist_api_python.http_requests import get

    endpoint = get_sync_url("items/get")
    data = {
        "item_id": item_id,
    }
    resource_data = get(api._session, endpoint, api._token, params=data)
    return resource_data


def enrich_comment(comment):
    """
    main goal is to add the posted_by_user_id to the comment
    so we can figure out who posted this
    """

    task_id = comment["task_id"]
    task_info = todoist_get_item_info(api, task_id)
    task_comments = task_info["notes"]

    # find the comment in the task comments
    matching_comments = [
        task_comment
        for task_comment in task_comments
        if task_comment["id"] == comment["id"]
    ]

    if len(matching_comments) != 1:
        raise Exception("Expected to find exactly one matching comment")

    task_comment = matching_comments[0]
    return comment | {"posted_by_user_id": task_comment["posted_uid"]}


def enrich_date(comment):
    return comment.__dict__ | {
        "posted_at_date": datetime.datetime.fromisoformat(
            comment.posted_at.replace("Z", "+00:00")
        )
    }


# each task content could contain markdown, we want to strip all markdown links but retain everything else
def strip_markdown_links(task_content):
    pattern = r"\[.*?\]\(.*?\)"
    return re.sub(pattern, "", task_content)


def generate_markdown(task_map, comments_by_task_id):
    markdown = []
    for task_id, comments in comments_by_task_id.items():
        task = task_map[task_id]

        task_content = strip_markdown_links(task.content)

        markdown.append(
            f"## [{task_content}](https://todoist.com/showTask?id={task_id})"
        )

        markdown.append(comments | fp.lpluck("content") | fp.str_join("---"))

    return "\n\n".join(markdown)


api = None


@click.command()
@click.option("--last-synced", required=True, help="The last synced date.")
@click.option("--target-user", required=True, help="The target user.")
@click.option("--target-project", required=True, help="The target project.")
def main(last_synced, target_user, target_project):
    api_key = os.getenv("TODOIST_API_KEY")
    assert api_key is not None

    global api
    api = TodoistAPI(api_key)

    """
    Project(color='blue', comment_count=0, id='project_id', is_favorite=False, is_inbox_project=False, is_shared=True, is_team_inbox=False, name='Project_Name', order=14, parent_id=None, url='https://todoist.com/showProject?id=project_id', view_style='list')]
    """
    projects = api.get_projects()
    target_project_name = target_project
    target_project = fp.exactly_one(
        [project for project in projects if project.name == target_project_name]
    )
    target_project_id = target_project.id

    """
    Task(assignee_id=None, assigner_id=None, comment_count=1, is_completed=False, content='look into car tax credit [Program | Energy Office](https://energyoffice.colorado.gov/program)', created_at='2023-10-05T17:13:23.912168Z', creator_id='creator_id', description='how long do i need to own the car? Can i stack the credits?', due=None, id='task_id', labels=[], order=-3, parent_id=None, priority=1, project_id='project_id', section_id='section_id', url='https://todoist.com/showTask?id=task_id', sync_id=None)
    """
    tasks = api.get_tasks(project_id=target_project_id)

    task_map = (
        tasks
        | fp.group_by(lambda task: task.id)
        # TODO this seems messy, group_by returns an array
        | fp.walk_values(fp.exactly_one)
    )
    last_synced_date = parser.parse(last_synced)

    # TODO should be a fp way of doing this
    filter_user_id = fp.exactly_one(
        [
            collaborator_id
            for collaborator_id, collaborator in collaborator_map(api).items()
            if collaborator["email"] == target_user
        ]
    )

    """
    Comment(attachment=None, content='- Lorem ipsum dolor sit amet?\n- Consectetur adipiscing elit?', id='comment_id', posted_at='2023-10-16T16:02:55.059574Z', project_id=None, task_id='task_id')
    """

    comments = (
        tasks
        # get all comments for each relevant task
        | fp.lmap(lambda task: api.get_comments(task_id=task.id))
        | fp.flatten()
        | fp.lmap(enrich_date)
        # no date filter is applied, we don't want all comments
        | fp.lfilter(lambda comment: comment["posted_at_date"] > last_synced_date)
        # comments do not come with who created the comment by default, we need to hit a separate API to add this to the comment
        | fp.lmap(enrich_comment)
        # only select the comments posted by our target user
        | fp.lfilter(lambda comment: comment["posted_by_user_id"] == filter_user_id)
        | fp.sort(key="posted_at_date")
        # group by task
        | fp.group_by(lambda comment: comment["task_id"])
    )

    markdown = generate_markdown(task_map, comments)
    print(markdown)


if __name__ == "__main__":
    main()
