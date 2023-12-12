#!/usr/bin/env -S ipython -i

import os

from todoist_api_python.api import TodoistAPI

from run import *
from todoist_digest.patch import patch_todoist_api

patch_todoist_api()

api_key = os.getenv("TODOIST_API_KEY")
assert api_key is not None

global api
api = TodoistAPI(api_key)

target_project_id = project_id = 2321686459
last_synced_date = parser.parse("2023-12-08T16:36:30Z")
