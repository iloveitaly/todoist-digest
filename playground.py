#!/usr/bin/env -S ipython -i

import os

# TODO this does not autoreload, I wonder if there is a way to issue a custom hook
# NOTE IMPORTANT! MUST GO FIRST
import todoist_digest.patch as _

from todoist_digest import *

from todoist_api_python.api import TodoistAPI

start_keys = set(locals().keys())

api_key = os.getenv("TODOIST_API_KEY")
assert api_key is not None

global api
api = TodoistAPI(api_key)

target_project_id = project_id = 2321686459
target_project_name = os.getenv("TARGET_PROJECT")
last_synced_date = parser.parse("2023-12-08T16:36:30Z")
target_user = os.getenv("TARGET_USER")
filter_user_id = "6305953"

# TODO how to determine if a project is a team project?
projects = api.get_projects()
shared_projects = projects | fp.where_attr(is_shared=True) | fp.to_list()
collaborators = collaborator_map(api)


def enhance_state(state):
    return state | {
        "project_name": (
            projects | fp.where_attr(id=state["project_id"]) | fp.first()
        ).name
    }


collaborator_states = todoist_get_sync_resource(api, "collaborators")[
    "collaborator_states"
]
sharing_map = (
    collaborator_states
    | fp.where(is_deleted=False, state="active")
    | fp.group_by(itemgetter("user_id"))
)
",".join(sharing_map["2503564"] | fp.pluck("project_id"))

end_keys = locals().keys()
new_keys = set(end_keys) - start_keys
formatted_keys = "\n - ".join(new_keys)

print(
    f"""
Some example usage:

projects = api.get_projects()

Local variables:
 - {formatted_keys}
"""
)
