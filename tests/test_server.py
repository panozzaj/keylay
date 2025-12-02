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

    def test_simple_form_caps_lock_to_escape(self, client):
        """Test the common CAPS_LOCK -> ESCAPE mapping works correctly."""
        response = client.post(
            "/simple",
            data={
                "layout": "",
                "layout2": "-",
                "from1": "58",  # CAPS_LOCK keycode
                "to1": "ESCAPE",
            },
        )
        assert response.status_code == 200
        assert response.content_type == "application/vnd.android.package-archive"

        with zipfile.ZipFile(io.BytesIO(response.data)) as zf:
            kcm = zf.read("res/Q2.kcm").decode("utf-8")
            assert "map key 58 ESCAPE" in kcm

    def test_simple_form_multiple_mappings(self, client):
        """Test multiple key mappings are all included."""
        response = client.post(
            "/simple",
            data={
                "layout": "",
                "layout2": "-",
                "from1": "58",  # CAPS_LOCK
                "to1": "ESCAPE",
                "from2": "1",  # ESC key
                "to2": "CAPS_LOCK",
            },
        )
        assert response.status_code == 200

        with zipfile.ZipFile(io.BytesIO(response.data)) as zf:
            kcm = zf.read("res/Q2.kcm").decode("utf-8")
            assert "map key 58 ESCAPE" in kcm
            assert "map key 1 CAPS_LOCK" in kcm

    def test_simple_form_with_second_layout(self, client):
        """Test that selecting a second layout produces a two-layout APK."""
        response = client.post(
            "/simple",
            data={
                "layout": "",
                "layout2": "keyboard_layout_german.kcm",  # An actual layout
                "from1": "58",
                "to1": "ESCAPE",
            },
        )
        assert response.status_code == 200

        with zipfile.ZipFile(io.BytesIO(response.data)) as zf:
            # Two-layout APK should have both Q2.kcm and _f.kcm
            assert "res/Q2.kcm" in zf.namelist()
            assert "res/_f.kcm" in zf.namelist()

            kcm1 = zf.read("res/Q2.kcm").decode("utf-8")
            kcm2 = zf.read("res/_f.kcm").decode("utf-8")
            assert "map key 58 ESCAPE" in kcm1
            assert "map key 58 ESCAPE" in kcm2

    def test_simple_form_empty_mapping_ignored(self, client):
        """Test that empty from/to values are ignored."""
        response = client.post(
            "/simple",
            data={
                "layout": "",
                "layout2": "-",
                "from1": "58",
                "to1": "ESCAPE",
                "from2": "",  # Empty - should be ignored
                "to2": "CTRL_LEFT",
            },
        )
        assert response.status_code == 200

        with zipfile.ZipFile(io.BytesIO(response.data)) as zf:
            kcm = zf.read("res/Q2.kcm").decode("utf-8")
            assert "map key 58 ESCAPE" in kcm
            # CTRL_LEFT should NOT appear since from2 was empty
            assert "CTRL_LEFT" not in kcm
