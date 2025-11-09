import importlib
import sys


def test_posthog_capture_patch():
    vector_store = importlib.import_module("app.services.vector_store")

    original_posthog = sys.modules.get("posthog")

    class StubPosthog:
        def __init__(self) -> None:
            self.api_key = None
            self.project_api_key = "test-key"
            self.calls: list[tuple[str, dict]] = []

        def capture(self, event: str, **kwargs):  # pragma: no cover - invoked via shim
            self.calls.append((event, kwargs))
            return "ok"

    stub = StubPosthog()

    sys.modules["posthog"] = stub

    try:
        importlib.reload(vector_store)

        result = vector_store.posthog.capture(
            "user-123",
            "telemetry-event",
            {"foo": "bar"},
            extra="value",
        )

        assert result == "ok"
        assert stub.calls == [
            (
                "telemetry-event",
                {
                    "distinct_id": "user-123",
                    "properties": {"foo": "bar"},
                    "extra": "value",
                },
            )
        ]
        assert stub.api_key == "test-key"
    finally:
        if original_posthog is None:
            sys.modules.pop("posthog", None)
        else:
            sys.modules["posthog"] = original_posthog
        importlib.reload(vector_store)
