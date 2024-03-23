import logging

import backoff
import requests
import todoist_api_python.http_requests

# backoff does not log by default
logging.getLogger("backoff").addHandler(logging.StreamHandler())


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

        # raw response on 429
        # b'{"error":"Too many requests. Limits reached. Try again later","error_code":35,"error_extra":{"event_id":"07c3fb965eaa4ec6a42e977c3e035c6b","retry_after":66},"error_tag":"LIMITS_REACHED","http_code":429}'

        # TODO pretty sure authorization errors are retried :/
        patched_function = backoff.on_exception(
            backoff.expo, requests.exceptions.HTTPError, max_tries=30
        )(original_function)

        setattr(
            todoist_api_python.http_requests,
            target,
            patched_function,
        )
