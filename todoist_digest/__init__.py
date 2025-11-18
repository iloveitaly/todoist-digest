import todoist_digest.patch as _  # isort: split

import funcy_pipe as fp

# extend funcy with all of the helpful additions I like :)
fp.patch()  # isort: split

import datetime
import os
import re
from functools import lru_cache

import click
import funcy as f
from dateutil import parser
from todoist_api_python.api import TodoistAPI
from todoist_api_python.models import Section
from whatever import that
from whenever import Instant

from .email import send_markdown_email
from .templates import render_template
from .todoist import (
    todoist_get_completed_activity,
    todoist_get_item_info,
    todoist_get_sync_resource,
)
from .util import TEMPLATES_DIRECTORY, log

# redirect to stderr so we can collect markdown from stdout
# handler = logging.StreamHandler(sys.stderr)
# log.addHandler(handler)


@lru_cache(maxsize=None)
def section_map(api: TodoistAPI) -> dict[int, Section]:
    # TODO should probably filter by project_id
    sections = api.get_sections(limit=200) | fp.lflatten()

    # TODO this api response does not seem to page
    # assert sections.has_more is False

    return sections | fp.group_by(that.project_id)


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
    if len(completed_activity["results"]) != 1:
        log.warning(
            "expected exactly one completion activity, got multiple, first one will be picked",
            count=len(completed_activity["results"]),
            task_id=task["id"],
        )

    if len(completed_activity["results"]) == 0:
        log.warning("Expected at least one completion activity")
        return task | {"initiator_id": None}

    event = completed_activity["results"][0]

    return task | {"initiator_id": event["initiator_id"]}


def object_to_dict(obj):
    return obj.__dict__


def strip_markdown_links(task_content):
    """
    each task content could contain markdown, we want to strip all markdown links but retain all other formatting
    """
    pattern = r"\[(.*?)\]\(.*?\)"
    return re.sub(pattern, "\\1", task_content)


def generate_slug(text):
    """
    Generate a URL slug from text by replacing spaces with dashes 
    and removing special characters
    """
    # Convert to lowercase and replace spaces with dashes
    slug = text.lower().replace(" ", "-")
    # Remove special characters, keeping only alphanumeric and dashes
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    # Remove multiple consecutive dashes
    slug = re.sub(r"-+", "-", slug)
    # Strip leading/trailing dashes
    slug = slug.strip("-")
    return slug


def todoist_task_link(task_id, task_content):
    """
    Generate the new Todoist task URL format: 
    https://app.todoist.com/app/task/<slug>-<task_id>
    """
    slug = generate_slug(task_content)
    return f"https://app.todoist.com/app/task/{slug}-{task_id}"


def todoist_project_link(project_id, project_name):
    """
    Generate the new Todoist project URL format:
    https://app.todoist.com/app/project/<project_slug>-<project_id>
    """
    slug = generate_slug(project_name)
    return f"https://app.todoist.com/app/project/{slug}-{project_id}"


def generate_markdown_for_new_tasks(new_tasks: list) -> list[dict] | None:
    if not new_tasks:
        return None

    render_nodes = []
    for task in new_tasks:
        task_content = strip_markdown_links(task["content"])

        render_nodes.append(
            {"task_content": task_content, "task_link": todoist_task_link(task["id"], task_content)}
        )

    return render_nodes


def generate_render_nodes_for_comments(
    task_map, comments_by_task_id: dict
) -> list[dict] | None:
    if not comments_by_task_id:
        return None

    render_nodes = []

    for task_id, comments in comments_by_task_id.items():
        task = task_map[task_id]

        task_content = strip_markdown_links(task.content)

        def add_content_to_attachments(comment):
            if comment["content"] != "":
                return comment

            return comment | {"content": comment["attachment"].file_name}

        transformed_comments = (
            comments
            | fp.map(add_content_to_attachments)
            | fp.map(
                lambda comment: comment
                | {"content": strip_markdown_links(comment["content"])}
            )
            | fp.to_list()
        )

        render_nodes.append(
            {
                "task_content": task_content,
                "task_link": todoist_task_link(task_id, task_content),
                "comments": transformed_comments,
            }
        )

    return render_nodes


def generate_markdown_for_completed_tasks(completed_tasks: list) -> list[dict] | None:
    if not completed_tasks:
        return None

    render_nodes = []

    for task in completed_tasks:
        task_content = strip_markdown_links(task["content"])
        render_nodes.append(
            {
                "task_content": task_content,
                "task_link": todoist_task_link(task["id"], task_content),
            }
        )

    return render_nodes


def get_api():
    api_key = os.getenv("TODOIST_API_KEY")
    assert api_key is not None
    return TodoistAPI(api_key)


# https://developer.todoist.com/sync/v9/#get-archived-sections
def get_completed_tasks(api: TodoistAPI, project_id):
    """
    The todoist API is such a dumpster fire:

    - can only pull last 30d
    - cannot filter by project ID, but have name
    - requires UTZ timezones otherwise you'll get incorrect data
    - returns a iterator of lists
    """

    project = api.get_project(project_id)
    return (
        api.get_completed_tasks_by_completion_date(
            since=Instant.now().add(hours=-30 * 24).py_datetime(),
            until=Instant.now().to_fixed_offset().py_datetime(),
            filter_query=f"#{project.name}",
            limit=200,
        )
        | fp.lflatten()
    )


def project_digest(api, last_synced, target_user, projects, target_project_name_or_id):
    """
    Project(color='blue', comment_count=0, id='project_id', is_favorite=False, is_inbox_project=False, is_shared=True, is_team_inbox=False, name='Project_Name', order=14, parent_id=None, url='https://todoist.com/showProject?id=project_id', view_style='list')]
    """

    # if digit, then a ID and not a name was passed
    if target_project_name_or_id.isdigit():
        target_project_id = target_project_name_or_id

        # in this case, the target_project_name is NOT the actual name!
        target_project = projects | fp.where_attr(id=target_project_id) | fp.first()
        target_project_name = target_project.name
    else:
        target_project_name = target_project_name_or_id
        target_project = projects | fp.where_attr(name=target_project_name) | fp.first()

        if not target_project:
            raise Exception(f"Could not find project with name {target_project_name}")

        target_project_id = target_project.id

    log.info(f"getting completed tasks {target_project_name}")
    completed_tasks = get_completed_tasks(api, target_project_id)

    log.info(f"getting tasks {target_project_name}")
    tasks = api.get_tasks(project_id=target_project_id) | fp.lflatten()

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

    log.info(f"getting comments {target_project_name}")

    comments = (
        all_tasks
        # get_comments will return comments for a completed task
        # TODO maybe use partialmethod to eliminate the partial here
        | fp.lmap(lambda task: api.get_comments(task_id=task.id))
        | fp.flatten()
        | fp.lmap(object_to_dict)
        # no date filter is applied by default, we don't want all comments
        | fp.lfilter(lambda comment: comment["posted_at"] > last_synced)
        # only select the comments posted by our target user
        | fp.where(poster_id=filter_user_id)
        | fp.sort(key="posted_at")
        # group by task
        | fp.group_by(lambda comment: comment["task_id"])
    )

    filtered_completed_tasks = (
        completed_tasks
        # old tasks drop the completed_at field
        | fp.where_not_attr(completed_at=None)
        | fp.lfilter(lambda task: task.completed_at > last_synced)
        | fp.lmap(object_to_dict)
        # enrichment to get the initiator_id
        | fp.lmap(f.partial(enrich_completed_tasks, api))
        | fp.where(initiator_id=filter_user_id)
        | fp.to_list()
    )

    log.info(f"getting new tasks {target_project_name}")

    last_synced_date_for_todoist_filter = last_synced.strftime("%m/%d/%Y")

    todoist_new_task_filter = (
        f"#{target_project_name} & created after: {last_synced_date_for_todoist_filter}"
    )

    new_tasks = (
        api.filter_tasks(query=todoist_new_task_filter, limit=200)
        | fp.flatten()
        | fp.lmap(object_to_dict)
        | fp.where(creator_id=filter_user_id, parent_id=None)
        # exclude any tasks which are already reported in the comments
        | fp.lfilter(lambda task: task["id"] not in comments.keys())
    )

    return {
        "project_id": target_project_id,
        "project_name": target_project_name,
        "comments": generate_render_nodes_for_comments(task_map, comments),
        "new_tasks": generate_markdown_for_new_tasks(new_tasks),
        "completed_tasks": generate_markdown_for_completed_tasks(
            filtered_completed_tasks
        ),
    }


def main(last_synced, target_user, target_project, email_auth, email_to, omit_empty):
    api = get_api()
    projects = api.get_projects() | fp.lflatten()
    last_synced_date = parser.parse(last_synced)

    # allow multiple projects to be passed in via a comma separated list
    if "," in target_project:
        target_projects = target_project.split(",") | fp.map(str.strip) | fp.compact()
    else:
        target_projects = [target_project]

    project_digests = target_projects | fp.lmap(
        fp.partial(project_digest, api, last_synced_date, target_user, projects)
    )

    formatted_project_header = ", ".join(project_digests | fp.lpluck("project_name"))

    def render_digest(digest):
        return render_template(
            TEMPLATES_DIRECTORY / "message.jinja",
            {
                "omit_empty": omit_empty,
                "target_user": target_user,
                "project_name": digest["project_name"],
                "project_id": digest["project_id"],
                "project_link": todoist_project_link(digest["project_id"], digest["project_name"]),
                "comments": digest["comments"],
                "new_tasks": digest["new_tasks"],
                "completed_tasks": digest["completed_tasks"],
            }
        )

    markdown = project_digests | fp.map(render_digest) | fp.join_str("\n")

    log.debug("generated project markdown", markdown=markdown)

    # Check if there are any updates across all project digests
    has_updates = any(
        digest["comments"] or digest["new_tasks"] or digest["completed_tasks"]
        for digest in project_digests
    )

    if not has_updates:
        log.info("No updates to report, skipping email")
        return

    if email_auth:
        now_time_formatted = datetime.datetime.now().strftime("%m/%d")
        last_synced_date_formatted = last_synced_date.strftime("%m/%d")

        send_markdown_email(
            email_auth,
            markdown,
            f"{last_synced_date_formatted}-{now_time_formatted} Todoist Digest for {formatted_project_header}",
            email_to,
        )


@click.command(context_settings={"auto_envvar_prefix": "TODOIST_DIGEST"})
@click.option("--last-synced", required=True, help="The last synced date")
@click.option("--target-user", required=True, help="The target user")
@click.option("--target-project", required=True, help="The target project")
@click.option("--email-auth", required=False, help="Authorization URL for SMTP emailer")
@click.option(
    "--omit-empty",
    is_flag=True,
    help="Omit empty sections from the digest content",
    default=True,
)
@click.option(
    "--email-to",
    required=False,
    help="Email(s) to send digest to. Separate multiple emails with a comma.",
)
def cli(last_synced, target_user, target_project, email_auth, email_to, omit_empty):
    main(last_synced, target_user, target_project, email_auth, email_to, omit_empty)


if __name__ == "__main__":
    cli()
