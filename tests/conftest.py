import pytest

# Fixtures that start `aea run` subprocesses (OpenTelemetry allows one tracer provider per process).
_SUBPROCESS_FIXTURES = {"runs", "price_runs", "check_runs"}


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if _SUBPROCESS_FIXTURES & set(getattr(item, "fixturenames", ())):
            item.add_marker(pytest.mark.slow)
