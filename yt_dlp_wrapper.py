#!/usr/bin/env python3
"""Simple HTTP wrapper for yt-dlp --flat-playlist --dump-single-json."""

import json
import os
import subprocess
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

# Find yt-dlp in common locations
YT_DLP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv", "bin", "yt-dlp")
if not os.path.exists(YT_DLP_PATH):
    YT_DLP_PATH = "yt-dlp"  # fallback to PATH


class YtDlpHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/playlist":
            self.send_response(404)
            self.end_headers()
            return

        url = urllib.parse.parse_qs(parsed.query).get("url", [None])[0]
        if not url:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'{"error": "No url parameter"}')
            return

        try:
            result = subprocess.run(
                [YT_DLP_PATH, "--flat-playlist", "--dump-single-json", url],
                capture_output=True, text=True, timeout=60
            )
            if result.returncode != 0:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "yt-dlp failed", "detail": result.stderr[:500]}).encode())
                return

            json.loads(result.stdout)  # parse but use stdout directly
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(result.stdout.encode())
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 9876), YtDlpHandler)
    print("yt-dlp wrapper running on :9876")
    server.serve_forever()
