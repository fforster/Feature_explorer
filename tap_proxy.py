#!/usr/bin/env python3
"""Local server for feature_explorer.html while tap.alerce.online does not send CORS headers.

Serves this directory and forwards /tap/* to the ALeRCE TAP service, so the page can
query TAP from the same origin. Standard library only.

    python3 tap_proxy.py            # then open http://localhost:8765/feature_explorer.html
    python3 tap_proxy.py --port 9000

Once the TAP service sends `Access-Control-Allow-Origin`, the page talks to it directly
(it tries https://tap.alerce.online/tap first) and this proxy is no longer needed.
"""
import argparse
import http.server
import os
import urllib.error
import urllib.request

UPSTREAM = "https://tap.alerce.online"
HERE = os.path.dirname(os.path.abspath(__file__))


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=HERE, **kwargs)

    def _proxy(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        req = urllib.request.Request(UPSTREAM + self.path, data=body, method=self.command)
        if self.headers.get("Content-Type"):
            req.add_header("Content-Type", self.headers["Content-Type"])
        req.add_header("User-Agent", "feature-explorer-tap-proxy")
        try:
            resp = urllib.request.urlopen(req, timeout=300)
            status, ctype, data = resp.status, resp.headers.get("Content-Type"), resp.read()
        except urllib.error.HTTPError as e:  # TAP errors come back as VOTable documents
            status, ctype, data = e.code, e.headers.get("Content-Type"), e.read()
        except Exception as e:  # network failure / timeout
            status, ctype, data = 502, "text/plain", f"proxy error: {e}".encode()
        self.send_response(status)
        self.send_header("Content-Type", ctype or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith("/tap/"):
            return self._proxy()
        return super().do_GET()

    def do_POST(self):
        if self.path.startswith("/tap/"):
            return self._proxy()
        self.send_error(405)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    server = http.server.ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Serving {HERE}\nOpen http://localhost:{args.port}/feature_explorer.html  (TAP proxied to {UPSTREAM})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
