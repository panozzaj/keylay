"""Command-line interface for keylay."""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description="Generate custom Android keyboard layout APKs")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Server command
    server_parser = subparsers.add_parser("serve", help="Run the web server")
    server_parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    server_parser.add_argument("--port", type=int, default=8080, help="Port to listen on")
    server_parser.add_argument("--debug", action="store_true", help="Enable debug mode")

    # Build command
    build_parser = subparsers.add_parser("build", help="Build an APK from a layout file")
    build_parser.add_argument("layout", help="Path to primary KCM layout file")
    build_parser.add_argument("--layout2", help="Path to secondary KCM layout file")
    build_parser.add_argument(
        "-o", "--output", default="keyboard-layout.apk", help="Output APK path"
    )

    args = parser.parse_args()

    if args.command == "serve":
        from .server import run_server

        run_server(host=args.host, port=args.port, debug=args.debug)

    elif args.command == "build":
        from pathlib import Path
        from .apk_builder import create_builder_from_env

        layout = Path(args.layout).read_text()
        layout2 = Path(args.layout2).read_text() if args.layout2 else None

        builder = create_builder_from_env()
        apk_bytes = builder.build_apk(layout, layout2)

        output_path = Path(args.output)
        output_path.write_bytes(apk_bytes)
        print(f"Built APK: {output_path}")


if __name__ == "__main__":
    main()
