"""
Todoist API extensions, mostly around the sync API, that won't be added to the core API (I tried)
"""

from functools import lru_cache


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


def todoist_get_completed_activity(api, task_id):
    from todoist_api_python.endpoints import get_sync_url
    from todoist_api_python.http_requests import get

    endpoint = get_sync_url("activity/get")
    data = {
        "limit": 100,
        "event_type": "completed",
        "object_id": task_id,
        "object_type": "item",
    }
    resource_data = get(api._session, endpoint, api._token, params=data)
    return resource_data
