import httpx
import pytest
import todoist_api_python._core.http_requests as hr

from todoist_digest.patch import patch_todoist_api


@pytest.mark.parametrize("status_code", [500, 502, 503, 504])
def test_retry_on_server_error(
    monkeypatch: pytest.MonkeyPatch, status_code: int
) -> None:
    attempts = 0

    def mock_get(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        req = httpx.Request("GET", "https://api.todoist.com")
        if attempts < 2:
            resp = httpx.Response(status_code, request=req)
            raise httpx.HTTPStatusError(
                f"{status_code} Server Error", request=req, response=resp
            )
        return "ok"

    monkeypatch.setattr(hr, "get", mock_get)
    if hasattr(patch_todoist_api, "complete"):
        monkeypatch.delattr(patch_todoist_api, "complete")

    # Use a faster backoff generator during tests so we don't delay
    monkeypatch.setattr(
        "backoff.expo",
        lambda *args, **kwargs: (0.01 for _ in range(10)),
    )

    patch_todoist_api()
    assert hr.get() == "ok"
    assert attempts == 2


def test_retry_on_429(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0

    def mock_get(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        req = httpx.Request("GET", "https://api.todoist.com")
        if attempts < 2:
            resp = httpx.Response(
                429,
                request=req,
                json={"error_extra": {"retry_after": 0}},
            )
            raise httpx.HTTPStatusError(
                "429 Too Many Requests", request=req, response=resp
            )
        return "ok"

    monkeypatch.setattr(hr, "get", mock_get)
    if hasattr(patch_todoist_api, "complete"):
        monkeypatch.delattr(patch_todoist_api, "complete")

    # Use a faster runtime backoff in tests
    monkeypatch.setattr(
        "todoist_digest.patch.extract_retry_time",
        lambda *args, **kwargs: 0.01,
        raising=False,
    )
    # Or mock backoff.runtime
    monkeypatch.setattr(
        "backoff.runtime",
        lambda *args, **kwargs: (0.01 for _ in range(10)),
    )

    patch_todoist_api()
    assert hr.get() == "ok"
    assert attempts == 2


@pytest.mark.parametrize("status_code", [404, 501])
def test_giveup_on_unretryable(
    monkeypatch: pytest.MonkeyPatch, status_code: int
) -> None:
    attempts = 0

    def mock_get(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        req = httpx.Request("GET", "https://api.todoist.com")
        resp = httpx.Response(status_code, request=req)
        raise httpx.HTTPStatusError(f"{status_code} Error", request=req, response=resp)

    monkeypatch.setattr(hr, "get", mock_get)
    if hasattr(patch_todoist_api, "complete"):
        monkeypatch.delattr(patch_todoist_api, "complete")

    patch_todoist_api()
    with pytest.raises(httpx.HTTPStatusError):
        hr.get()

    assert attempts == 1
