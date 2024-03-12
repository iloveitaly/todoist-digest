import logging

from todoist_digest.patch import patch_todoist_api  # isort: split

patch_todoist_api()  # isort: split

import datetime
import inspect
import logging
import os
import re
import sys
from functools import lru_cache

import click
import funcy as f
import funcy_pipe as fp
from dateutil import parser
from todoist_api_python.api import TodoistAPI
from todoist_api_python.models import Section
from whatever import that

from todoist_digest.email import send_markdown_email
from todoist_digest.todoist import (
    todoist_get_completed_activity,
    todoist_get_item_info,
    todoist_get_sync_resource,
)

# extend funcy with all of the helpful additions I like :)
fp.patch()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# redirect to stderr so we can collect markdown from stdout
handler = logging.StreamHandler(sys.stderr)
logger.addHandler(handler)

# conditionally import pretty traceback
try:
    import pretty_traceback

    pretty_traceback.install()
except ImportError:
    pass


@lru_cache(maxsize=None)
def section_map(api: TodoistAPI) -> dict[int, Section]:
    # TODO should probably filter by project_id
    sections = api.get_sections()

    # TODO this api response does not seem to page
    # assert sections.has_more is False

    return sections | fp.group_by(f.compose(int, that.project_id))


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

    # there can be multiple completed events, I'm guessing if people complete > uncomplete > complete a task
    if len(completed_activity["events"]) != 1:
        # raise Exception("Expected exactly one completion activity")
        pass

    if len(completed_activity["events"]) == 0:
        logger.warning("Expected at least one completion activity")
        return task | {"initiator_id": None}

    event = completed_activity["events"][0]

    return task | {"initiator_id": event["initiator_id"]}


def enrich_comment(comment):
    """
    main goal is to add the posted_by_user_id to the comment
    so we can figure out who posted this
    """

    api = get_api()
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


def enrich_date(comment, key):
    """
    Convert posted at date to a datetime object
    """
    return comment | {f"{key}_date": parse_todoist_date(comment[key])}


def strip_markdown_links(task_content):
    """
    each task content could contain markdown, we want to strip all markdown links but retain all other formatting
    """
    pattern = r"\[(.*?)\]\(.*?\)"
    return re.sub(pattern, "\\1", task_content)


def task_link(task_id):
    return f"https://todoist.com/showTask?id={task_id}"


def generate_markdown_for_new_tasks(new_tasks: list) -> str:
    if not new_tasks:
        return "*No new tasks*"

    markdown = []
    for task in new_tasks:
        task_content = strip_markdown_links(task["content"])

        markdown.append(f"## [{task_content}]({task_link(task['id'])})")

    return "\n\n".join(markdown)


def generate_markdown_for_comments(task_map, comments_by_task_id: dict) -> str:
    if not comments_by_task_id:
        return "*No comments*"

    markdown = []
    for task_id, comments in comments_by_task_id.items():
        task = task_map[task_id]

        task_content = strip_markdown_links(task.content)

        markdown.append(f"## [{task_content}]({task_link(task_id)})")

        def add_content_to_attachments(comment):
            if comment["content"] != "":
                return comment

            return comment | {"content": comment["attachment"].file_name}

        def format_content(comment):
            formatted_date = comment["posted_at_date"].strftime("%m/%d")
            content = comment["content"]

            return f"_{formatted_date}_: {content}"

        markdown.append(
            comments
            | fp.map(add_content_to_attachments)
            | fp.map(
                lambda comment: comment
                | {"content": strip_markdown_links(comment["content"])}
            )
            # | fp.where_not(content='')
            | fp.map(format_content)
            # separate each comment with a line
            | fp.str_join("\n\n---\n\n")
        )

    return "\n\n".join(markdown)


def generate_markdown_for_completed_tasks(completed_tasks: list) -> str:
    if not completed_tasks:
        return "*No completed tasks*"

    markdown = []
    for task in completed_tasks:
        task_content = strip_markdown_links(task["content"])

        markdown.append(f"## [{task_content}]({task_link(task['id'])})")

    return "\n\n".join(markdown)


def get_api():
    api_key = os.getenv("TODOIST_API_KEY")
    assert api_key is not None
    return TodoistAPI(api_key)


# https://developer.todoist.com/sync/v9/#get-archived-sections
def get_completed_tasks(api: TodoistAPI, project_id):
    """
    you have to iterate over all sections in a project to get all completed tasks

    data structure:

        'completed_info',
        'from_dict',
        'has_more',
        'items',
        'next_cursor',
        'total'
    """

    # combine all projects and subsections into a single list with params that correspond to the API params required
    projects_and_sections = [
        {"section_id": section_id}
        for section_id in section_map(api)[int(project_id)] | fp.lmap(that.id)
    ] + [{"project_id": project_id}]

    def get_all_completed_items(original_params: dict):
        params = original_params.copy()
        results = []

        while True:
            # 100 is the limit for this particular completed items endpoint, the REST API allows for max of 200 :/
            # https://github.com/Suor/funcy/issues/148
            response = api.get_completed_items(**(params | {"limit": 100}))
            results.append(response.items)

            if not response.has_more:
                break

            params["cursor"] = response.next_cursor

        return f.flatten(results)

    # TODO could be neat if there was some sort of kwargs partial here
    return (
        projects_and_sections
        | fp.lmap(get_all_completed_items)
        | fp.flatten()
        | fp.to_list()
    )


def main(last_synced, target_user, target_project, email_auth, email_to):
    api = get_api()
    target_project_name = target_project

    """
    Project(color='blue', comment_count=0, id='project_id', is_favorite=False, is_inbox_project=False, is_shared=True, is_team_inbox=False, name='Project_Name', order=14, parent_id=None, url='https://todoist.com/showProject?id=project_id', view_style='list')]
    """
    logger.info("getting projects")

    if target_project.isdigit():
        target_project_id = target_project

        # in this case, the target_project_name is NOT the actual name!
        projects = api.get_projects()
        target_project = projects | fp.where_attr(id=target_project_id) | fp.first()
        target_project_name = target_project.name
    else:
        projects = api.get_projects()
        target_project = projects | fp.where_attr(name=target_project_name) | fp.first()

        if not target_project:
            raise Exception(f"Could not find project with name {target_project_name}")

        target_project_id = target_project.id

    logger.info("getting completed tasks")
    completed_tasks = get_completed_tasks(api, target_project_id)

    logger.info("getting tasks")
    tasks = api.get_tasks(project_id=target_project_id)

    all_tasks = tasks + completed_tasks

    """
    Task(assignee_id=None, assigner_id=None, comment_count=1, is_completed=False, content='look into car tax credit [Program | Energy Office](https://energyoffice.colorado.gov/program)', created_at='2023-10-05T17:13:23.912168Z', creator_id='creator_id', description='how long do i need to own the car? Can i stack the credits?', due=None, id='task_id', labels=[], order=-3, parent_id=None, priority=1, project_id='project_id', section_id='section_id', url='https://todoist.com/showTask?id=task_id', sync_id=None)
    """
    # used to lookup tasks when generating comment markdown
    task_map = dict(
        # does not contain completed tasks!
        all_tasks
        # TODO shouldn't need a lamda here
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

    logger.info("getting comments")

    comments = (
        all_tasks
        # get_comments will return comments for a completed task
        # TODO maybe use partialmethod to eliminate the partial here
        | fp.lmap(lambda task: api.get_comments(task_id=task.id))
        | fp.flatten()
        | fp.lmap(object_to_dict)
        | fp.lmap(fp.partial(enrich_date, key="posted_at"))
        # no date filter is applied by default, we don't want all comments
        | fp.lfilter(lambda comment: comment["posted_at_date"] > last_synced_date)
        # comments do not come with who created the comment by default, we need to hit a separate API to add this to the comment
        | fp.lmap(enrich_comment)
        # only select the comments posted by our target user
        | fp.where(posted_by_user_id=filter_user_id)
        | fp.sort(key="posted_at_date")
        # group by task
        | fp.group_by(lambda comment: comment["task_id"])
    )

    filtered_completed_tasks = (
        completed_tasks
        | fp.lfilter(
            lambda comment: parse_todoist_date(comment.completed_at) > last_synced_date
        )
        | fp.lmap(object_to_dict)
        | fp.lmap(f.partial(enrich_completed_tasks, api))
        | fp.where(initiator_id=filter_user_id)
        | fp.to_list()
    )

    logger.info("getting new tasks")
    last_synced_date_for_todoist_filter = last_synced_date.strftime("%m/%d/%Y")
    new_tasks = (
        api.get_tasks(
            filter=f"#{target_project_name} & created after: {last_synced_date_for_todoist_filter}",
        )
        | fp.lmap(object_to_dict)
        | fp.where(creator_id=filter_user_id, parent_id=None)
        # exclude any tasks which are already reported in the comments
        | fp.filter(lambda task: task["id"] not in comments.keys())
        | fp.to_list()
    )

    markdown = f"""
_targeting user {target_user} on project {target_project_name}_

# Comments on Project {target_project_name}
{generate_markdown_for_comments(task_map, comments)}

# Added Tasks on Project {target_project_name}
{generate_markdown_for_new_tasks(new_tasks)}

# Completed Tasks on Project {target_project_name}
{generate_markdown_for_completed_tasks(filtered_completed_tasks)}
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


@click.command()
@click.option("--last-synced", required=True, help="The last synced date.")
@click.option("--target-user", required=True, help="The target user.")
@click.option("--target-project", required=True, help="The target project.")
@click.option("--email-auth", required=False, help="Authorization URL for SMTP emailer")
@click.option("--email-to", required=False, help="Email to send digest to")
def cli(last_synced, target_user, target_project, email_auth, email_to):
    main(last_synced, target_user, target_project, email_auth, email_to)


if __name__ == "__main__":
    cli()
