#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["flask>=3.1,<4"]
# ///
"""runs the site locally: rebuilds each track's data, then starts the Flask app (app.py) in debug mode, so accounts
and syncing work the same as on butterbricks.org. The local database is instance/butterbricks.db and the invite code
is "dev" unless INVITE_CODE is set"""

import sys

import build


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    build.main()
    from app import INVITE_CODE, app
    print(f"serving on http://localhost:{port} (invite code: {INVITE_CODE or 'sign-up closed'})", flush=True)
    app.run(host="127.0.0.1", port=port, debug=True, use_reloader=False)


if __name__ == "__main__":
    main()
