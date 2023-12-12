from todoist_digest.email import send_markdown_email

from todoist_digest.patch import patch_todoist_api  # isort: split

patch_todoist_api()  # isort: split

import datetime
import os
import re
from functools import lru_cache

import click
import funcy as f
import funcy_pipe as fp
from dateutil import parser
from funcy_pipe.pipe import PipeFirst
from todoist_api_python.api import TodoistAPI
from todoist_api_python.models import Collaborator

from todoist_digest.todoist import (
    todoist_get_completed_activity,
    todoist_get_item_info,
    todoist_get_sync_resource,
)

# conditionally import pretty traceback
try:
    import pretty_traceback

    pretty_traceback.install()
except ImportError:
    pass


# https://github.com/Suor/funcy/pull/140
def where_attr(objects, **cond):
    items = cond.items()
    match = lambda obj: all(hasattr(obj, k) and getattr(obj, k) == v for k, v in items)
    return filter(match, objects)


f.where_attr = where_attr
fp.where_attr = PipeFirst(where_attr)


@lru_cache(maxsize=None)
def collaborator_map(api):
    """
    returns a map of collaborator_id -> collaborator
    """
    result = todoist_get_sync_resource(api, "collaborators")
    collaborators = result["collaborators"]

    return {collaborator["id"]: collaborator for collaborator in collaborators}


def enrich_completed_tasks(api, task):
    completed_activity = todoist_get_completed_activity(api, task["id"])

    if len(completed_activity["events"]) != 1:
        raise Exception("Expected exactly one completion activity")

    event = completed_activity["events"][0]

    return task | {"initiator_id": event["initiator_id"]}


def enrich_comment(comment):
    """
    main goal is to add the posted_by_user_id to the comment
    so we can figure out who posted this
    """

    task_id = comment["task_id"]
    task_info = todoist_get_item_info(api, task_id)
    task_comments = task_info["notes"]

    # TODO there's got to be a better way to do this with funcy
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


def parse_todoist_date(date_string):
    return datetime.datetime.fromisoformat(date_string.replace("Z", "+00:00"))


def object_to_dict(obj):
    return obj.__dict__


def enrich_date(comment):
    return comment | {"posted_at_date": parse_todoist_date(comment["posted_at"])}


# each task content could contain markdown, we want to strip all markdown links but retain everything else
def strip_markdown_links(task_content):
    pattern = r"\[(.*?)\]\(.*?\)"
    return re.sub(pattern, "\\1", task_content)


def generate_markdown_for_comments(task_map, comments_by_task_id):
    if not comments_by_task_id:
        return "*No comments*"

    markdown = []
    for task_id, comments in comments_by_task_id.items():
        task = task_map[task_id]

        task_content = strip_markdown_links(task.content)

        markdown.append(
            f"## [{task_content}](https://todoist.com/showTask?id={task_id})"
        )

        markdown.append(comments | fp.lpluck("content") | fp.str_join("---"))

    return "\n\n".join(markdown)


def generate_markdown_for_completed_tasks(completed_tasks):
    if not completed_tasks:
        return "*No completed tasks*"

    markdown = []
    for task in completed_tasks:
        task_content = strip_markdown_links(task["content"])

        markdown.append(
            f"## [{task_content}](https://todoist.com/showTask?id={task['id']})"
        )

    return "\n\n".join(markdown)


api = None


# https://developer.todoist.com/sync/v9/#get-archived-sections
def get_completed_tasks(api, project_id):
    """
    data structure:

    'completed_info',
    'from_dict',
    'has_more',
    'items',
    'next_cursor',
    'total'
    ]
    """

    completed_items = api.get_completed_items(project_id=project_id, limit=100)

    # TODO we will need to handle this as some point, could use last_seen_id instead

    assert completed_items.has_more is False

    return completed_items.items


@click.command()
@click.option("--last-synced", required=True, help="The last synced date.")
@click.option("--target-user", required=True, help="The target user.")
@click.option("--target-project", required=True, help="The target project.")
@click.option("--email-auth", required=False, help="Authorization URL for SMTP emailer")
@click.option("--email-to", required=False, help="Email to send digest to")
def cli(last_synced, target_user, target_project, email_auth, email_to):
    api_key = os.getenv("TODOIST_API_KEY")
    assert api_key is not None

    global api
    api = TodoistAPI(api_key)

    target_project_name = target_project

    """
    Project(color='blue', comment_count=0, id='project_id', is_favorite=False, is_inbox_project=False, is_shared=True, is_team_inbox=False, name='Project_Name', order=14, parent_id=None, url='https://todoist.com/showProject?id=project_id', view_style='list')]
    """
    projects = api.get_projects()
    target_project = projects | fp.where_attr(name=target_project_name) | fp.first()
    target_project_id = target_project.id

    """
    Task(assignee_id=None, assigner_id=None, comment_count=1, is_completed=False, content='look into car tax credit [Program | Energy Office](https://energyoffice.colorado.gov/program)', created_at='2023-10-05T17:13:23.912168Z', creator_id='creator_id', description='how long do i need to own the car? Can i stack the credits?', due=None, id='task_id', labels=[], order=-3, parent_id=None, priority=1, project_id='project_id', section_id='section_id', url='https://todoist.com/showTask?id=task_id', sync_id=None)
    """
    tasks = api.get_tasks(project_id=target_project_id)

    task_map = (
        tasks
        | fp.group_by(lambda task: task.id)
        # TODO this seems messy, group_by returns an array as the value so we extract the first element
        | fp.walk_values(fp.exactly_one)
    )

    last_synced_date = parser.parse(last_synced)

    filter_user_id = (
        collaborator_map(api).values()
        | fp.where(email=target_user)
        | fp.pluck("id")
        # exactly_once would be better here, but less performant
        | fp.first()
    )

    """
    Comment(attachment=None, content='- Lorem ipsum dolor sit amet?\n- Consectetur adipiscing elit?', id='comment_id', posted_at='2023-10-16T16:02:55.059574Z', project_id=None, task_id='task_id')
    """

    comments = (
        tasks
        # get all comments for each relevant task
        | fp.lmap(lambda task: api.get_comments(task_id=task.id))
        | fp.flatten()
        | fp.lmap(object_to_dict)
        | fp.lmap(enrich_date)
        # no date filter is applied by default, we don't want all comments
        | fp.lfilter(lambda comment: comment["posted_at_date"] > last_synced_date)
        # comments do not come with who created the comment by default, we need to hit a separate API to add this to the comment
        | fp.lmap(enrich_comment)
        # only select the comments posted by our target user
        | fp.lfilter(lambda comment: comment["posted_by_user_id"] == filter_user_id)
        | fp.sort(key="posted_at_date")
        # group by task
        | fp.group_by(lambda comment: comment["task_id"])
    )

    completed_tasks = (
        get_completed_tasks(api, target_project_id)
        | fp.lfilter(
            lambda comment: parse_todoist_date(comment.completed_at) > last_synced_date
        )
        | fp.lmap(object_to_dict)
        | fp.lmap(f.partial(enrich_completed_tasks, api))
        | fp.lfilter(lambda comment: comment["initiator_id"] == filter_user_id)
    )

    markdown = f"""
# Comments for {target_project_name}
{generate_markdown_for_comments(task_map, comments)}

# Completed Tasks for {target_project_name}
{generate_markdown_for_completed_tasks(completed_tasks)}
    """

    print(markdown)

    if email_auth:
        now_time_formatted = datetime.datetime.now().strftime("%m/%d")
        last_synced_date_formatted = last_synced_date.strftime("%m/%d")

        send_markdown_email(
            email_auth,
            markdown,
            f"{last_synced_date_formatted}-{now_time_formatted} Todoist Digest for {target_project_name}",
            email_to,
        )


if __name__ == "__main__":
    cli()