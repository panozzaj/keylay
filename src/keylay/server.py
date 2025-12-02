"""Flask web server for building keyboard layout APKs."""

import logging
from pathlib import Path

from flask import Flask, redirect, request, send_file, send_from_directory

from .apk_builder import ApkBuilder, create_builder_from_env
from .layouts import from_named_layout

logger = logging.getLogger(__name__)

RESOURCES_DIR = Path(__file__).parent.parent.parent / "resources"
PUBLIC_DIR = RESOURCES_DIR / "public"


def create_app(builder: ApkBuilder | None = None) -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)

    if builder is None:
        builder = create_builder_from_env()

    @app.route("/")
    def index():
        return redirect("/simple.html")

    @app.route("/simple", methods=["GET", "POST"])
    def simple():
        if request.method == "GET":
            return redirect("/simple.html")
        return build_apk_simple()

    @app.route("/complex", methods=["GET", "POST"])
    def complex_route():
        if request.method == "GET":
            return redirect("/complex.html")
        return build_apk_complex()

    @app.route("/docs")
    def docs():
        return send_from_directory(PUBLIC_DIR, "docs.html")

    @app.route("/<path:filename>")
    def static_files(filename):
        return send_from_directory(PUBLIC_DIR, filename)

    def build_apk_simple():
        """Build APK from simple form parameters."""
        layout_name = request.form.get("layout")
        layout2_name = request.form.get("layout2")

        # Collect key mappings from form
        mappings = {}
        for key, value in request.form.items():
            if key.startswith("from") and value:
                idx = key[4:]  # Get the number suffix
                to_key = request.form.get(f"to{idx}")
                if to_key:
                    mappings[value] = to_key

        # Generate layouts
        layout = from_named_layout(layout_name, mappings)

        if layout2_name and layout2_name != "-":
            layout2 = from_named_layout(layout2_name, mappings)
        else:
            layout2 = None

        return serve_apk(layout, layout2)

    def build_apk_complex():
        """Build APK from complex form with raw layout content."""
        layout = request.form.get("layout")
        if not layout:
            return "Missing layout", 400

        layout2 = request.form.get("layout2")
        return serve_apk(layout, layout2)

    def serve_apk(layout: str, layout2: str | None):
        """Build and serve an APK."""
        try:
            apk_bytes = builder.build_apk(layout, layout2)
        except Exception as e:
            logger.exception("Error building APK")
            return str(e), 500

        import io

        return send_file(
            io.BytesIO(apk_bytes),
            mimetype="application/vnd.android.package-archive",
            as_attachment=True,
            download_name="KeyboardLayout.apk",
        )

    return app


def run_server(host: str = "0.0.0.0", port: int = 8080, debug: bool = False):
    """Run the development server."""
    app = create_app()
    app.run(host=host, port=port, debug=debug)
