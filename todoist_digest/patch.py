import backoff
import requests
import todoist_api_python.http_requests


# https://github.com/Doist/todoist-api-python/issues/38
# backoff 5xx errors
def patch_todoist_api():
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
