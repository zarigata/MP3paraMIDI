"""Test scaffolding for the unified FastAPI + Flask + Gradio server."""

from __future__ import annotations

import os
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from src.main import create_unified_app

pytestmark = pytest.mark.main


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Provide a TestClient backed by the unified FastAPI application."""

    # Ensure predictable configuration during tests.
    monkeypatch.setenv("GRADIO_SHARE", "False")
    monkeypatch.delenv("GRADIO_AUTH", raising=False)

    app = create_unified_app()
    with TestClient(app) as test_client:
        yield test_client


def test_create_unified_app_returns_fastapi_instance():
    from fastapi import FastAPI

    app = create_unified_app()
    assert isinstance(app, FastAPI)
    assert app.title == "MP3paraMIDI"


def test_flask_root_route_accessible(client: TestClient):
    response = client.get("/")
    assert response.status_code in {200, 302}


def test_flask_health_route(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body.get("status") in {"healthy", "ok"}


def test_flask_api_method_not_allowed(client: TestClient):
    response = client.get("/api/separate")
    assert response.status_code in {404, 405}


def test_gradio_route_served(client: TestClient):
    response = client.get("/gradio")
    assert response.status_code in {200, 307}


def test_fastapi_health_endpoint(client: TestClient):
    response = client.get("/api/health-fastapi")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "framework": "fastapi"}


def test_static_assets(client: TestClient):
    css_response = client.get("/static/css/styles.css")
    js_response = client.get("/static/js/main.js")
    assert css_response.status_code in {200, 404}
    assert js_response.status_code in {200, 404}


@pytest.mark.slow
@pytest.mark.integration
@pytest.mark.skip("Real audio processing requires heavy dependencies and setup.")
def test_full_workflow_integration(client: TestClient, tmp_path):
    """Placeholder for an end-to-end integration test covering uploads and processing."""

    assert tmp_path  # Placeholder assertion to avoid lint warnings
