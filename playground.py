#!/usr/bin/env -S ipython -i

import os

from todoist_api_python.api import TodoistAPI

from todoist_digest.patch import patch_todoist_api

patch_todoist_api()

api_key = os.getenv("TODOIST_API_KEY")
assert api_key is not None

global api
api = TodoistAPI(api_key)

project_id = 2321686459
