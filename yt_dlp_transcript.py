#!/usr/bin/env python3
"""Download YouTube transcript via yt-dlp — runs on host."""
import json
import subprocess
import os
import tempfile
import shutil
import glob
from http.server import HTTPServer, BaseHTTPRequestHandler


class TranscriptHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != '/transcript':
            self.send_response(404)
            self.end_headers()
            return

        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        try:
            data = json.loads(body)
            video_id = data.get('video_id', '')
        except Exception:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'Invalid body'}).encode())
            return

        tmpdir = tempfile.mkdtemp()
        try:
            # Download auto-caption as SRT via yt-dlp
            cmd = [
                'yt-dlp', '--skip-download', '--write-auto-subs', '--sub-lang', 'en',
                '--convert-subs', 'srt', '--sub-format', 'srt',
                '-o', f'{tmpdir}/%(id)s.%(ext)s',
                f'https://www.youtube.com/watch?v={video_id}'
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            # yt-dlp may save as video_id.en.srt (with language code)
            srt_files = glob.glob(f'{tmpdir}/{video_id}*.srt')
            if srt_files:
                with open(srt_files[0]) as f:
                    srt = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'transcript': srt}).encode())
                return

            self.send_response(503)
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'No captions available', 'video_id': video_id}).encode())
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def log_message(self, format, *args):
        pass


if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', 9877), TranscriptHandler)
    print('Transcript wrapper running on :9877')
    server.serve_forever()
