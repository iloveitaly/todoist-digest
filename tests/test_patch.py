import httpx
import pytest
import todoist_api_python._core.http_requests as hr

from todoist_digest.patch import patch_todoist_api


def test_retry_on_503(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0

    def mock_get(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        req = httpx.Request("GET", "https://api.todoist.com")
        if attempts < 2:
            resp = httpx.Response(503, request=req)
            raise httpx.HTTPStatusError(
                "503 Service Unavailable", request=req, response=resp
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


def test_giveup_on_404(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0

    def mock_get(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        req = httpx.Request("GET", "https://api.todoist.com")
        resp = httpx.Response(404, request=req)
        raise httpx.HTTPStatusError("404 Not Found", request=req, response=resp)

    monkeypatch.setattr(hr, "get", mock_get)
    if hasattr(patch_todoist_api, "complete"):
        monkeypatch.delattr(patch_todoist_api, "complete")

    patch_todoist_api()
    with pytest.raises(httpx.HTTPStatusError):
        hr.get()

    assert attempts == 1
