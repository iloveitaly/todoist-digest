#!/usr/bin/env -S ipython -i

import os

from todoist_api_python.api import TodoistAPI

# TODO this does not autoreload, I wonder if there is a way to issue a custom hook
from todoist_digest import *
from todoist_digest.patch import patch_todoist_api

start_keys = set(locals().keys())

patch_todoist_api()

api_key = os.getenv("TODOIST_API_KEY")
assert api_key is not None

global api
api = TodoistAPI(api_key)

target_project_id = project_id = 2321686459
target_project_name = os.getenv("TARGET_PROJECT")
last_synced_date = parser.parse("2023-12-08T16:36:30Z")
target_user = os.getenv("TARGET_USER")
filter_user_id = "6305953"

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
