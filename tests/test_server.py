"""Tests for the web server."""

import io
import zipfile

import pytest

from keylay.apk_builder import create_builder_from_env
from keylay.server import create_app


@pytest.fixture
def client():
    """Create a test client."""
    builder = create_builder_from_env()
    app = create_app(builder)
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


class TestRoutes:
    def test_index_redirects(self, client):
        response = client.get("/")
        assert response.status_code == 302
        assert "/simple.html" in response.location

    def test_simple_get_redirects(self, client):
        response = client.get("/simple")
        assert response.status_code == 302

    def test_static_html(self, client):
        response = client.get("/simple.html")
        assert response.status_code == 200
        assert b"html" in response.data.lower()


class TestApkGeneration:
    def test_simple_form_builds_apk(self, client):
        response = client.post(
            "/simple",
            data={
                "layout": "",
                "from0": "58",
                "to0": "CTRL_LEFT",
            },
        )
        assert response.status_code == 200
        assert response.content_type == "application/vnd.android.package-archive"

        # Verify it's a valid APK
        with zipfile.ZipFile(io.BytesIO(response.data)) as zf:
            assert "META-INF/MANIFEST.MF" in zf.namelist()
            kcm = zf.read("res/Q2.kcm").decode("utf-8")
            assert "map key 58 CTRL_LEFT" in kcm

    def test_complex_form_builds_apk(self, client):
        response = client.post(
            "/complex",
            data={
                "layout": "type OVERLAY\nmap key 58 ESC\n",
            },
        )
        assert response.status_code == 200
        assert response.content_type == "application/vnd.android.package-archive"

    def test_complex_missing_layout_returns_400(self, client):
        response = client.post("/complex", data={})
        assert response.status_code == 400
