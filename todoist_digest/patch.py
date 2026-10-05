import logging

import backoff
import httpx
import httpx2
import requests
import todoist_api_python._core.http_requests

# backoff does not log by default
logging.getLogger("backoff").addHandler(logging.StreamHandler())


# https://github.com/Doist/todoist-api-python/issues/38
# backoff all non-200 errors
def patch_todoist_api():
    if hasattr(patch_todoist_api, "complete") and patch_todoist_api.complete:
        return

    patch_targets = [
        target
        for target in ["delete", "get", "json", "post"]
        if hasattr(todoist_api_python._core.http_requests, target)
    ]

    for target in patch_targets:
        original_function = getattr(todoist_api_python._core.http_requests, target)

        setattr(
            todoist_api_python._core.http_requests,
            f"original_{target}",
            original_function,
        )

        def extract_retry_time(exception):
            """
            raw response on 429:

            b'{"error":"Too many requests. Limits reached. Try again later","error_code":35,"error_extra":{"event_id":"07c3fb965eaa4ec6a42e977c3e035c6b","retry_after":66},"error_tag":"LIMITS_REACHED","http_code":429}'
            """
            if isinstance(exception, (httpx.HTTPStatusError, httpx2.HTTPStatusError)):
                if exception.response.status_code != 429:
                    raise exception
                try:
                    retry_after_in_seconds = (
                        exception.response.json()
                        .get("error_extra", {})
                        .get("retry_after", 10)
                    )
                except (ValueError, KeyError, AttributeError):
                    retry_after_in_seconds = 10
                return retry_after_in_seconds + 10

            if (
                not isinstance(exception, requests.exceptions.HTTPError)
                or exception.response is None
                or exception.response.status_code != 429
            ):
                raise exception

            retry_after_in_seconds = exception.response.json()["error_extra"][
                "retry_after"
            ]

            # add 10s of buffer
            return retry_after_in_seconds + 10

        patched_function = backoff.on_exception(
            backoff.runtime,
            (
                requests.exceptions.HTTPError,
                httpx.HTTPStatusError,
                httpx2.HTTPStatusError,
            ),
            value=extract_retry_time,
            max_tries=8,
        )(original_function)

        def should_giveup_503(exception):
            response = getattr(exception, "response", None)
            return response is None or response.status_code != 503

        patched_function_503 = backoff.on_exception(
            backoff.expo,
            (
                requests.exceptions.HTTPError,
                httpx.HTTPStatusError,
                httpx2.HTTPStatusError,
            ),
            giveup=should_giveup_503,
            max_tries=8,
        )(patched_function)

        patched_function2 = backoff.on_exception(
            backoff.expo,
            (
                requests.exceptions.RequestException,
                httpx.RequestError,
                httpx2.RequestError,
            ),
            giveup=lambda e: isinstance(e, requests.exceptions.HTTPError),
            max_tries=30,
        )(patched_function_503)

        setattr(
            todoist_api_python._core.http_requests,
            target,
            patched_function2,
        )

    patch_todoist_api.complete = True


patch_todoist_api()
