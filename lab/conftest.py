"""Shared test plumbing: integration option for the lab stack URL."""

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--lab-url",
        default="http://127.0.0.1:8100",
        help="shop_api base URL for integration tests",
    )


@pytest.fixture
def lab_url(request) -> str:
    return request.config.getoption("--lab-url")
