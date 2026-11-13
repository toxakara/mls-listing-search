from __future__ import annotations

from collections.abc import Iterator
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

# Recency depends on today's date, so the HTTP tests fix it to keep exact scores stable.
TODAY = date(2026, 11, 12)


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app(clock=lambda: TODAY)) as test_client:
        yield test_client
