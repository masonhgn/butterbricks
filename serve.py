#!/usr/bin/env python3
"""rebuilds the web data, then serves web/ with caching turned off, so edits (and other sites that used the same
port before) never leave stale files in the browser"""

import functools
import http.server
import os
import sys

import build_web

HERE = os.path.dirname(os.path.abspath(__file__))


class NoCache(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *args):
        pass


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    build_web.main()
    handler = functools.partial(NoCache, directory=os.path.join(HERE, "web"))
    print(f"serving on http://localhost:{port}")
    http.server.ThreadingHTTPServer(("", port), handler).serve_forever()


if __name__ == "__main__":
    main()
