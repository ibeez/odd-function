#!/usr/bin/env python3
"""Render the Fig. 06 loop to exports/odd-integral-loop.mp4 (H.264 + AAC, 1200 x 1000, 30 fps, 20 s).

Serves this folder, opens index.html?render in headless Chrome, encodes each frame the page posts
with OpenCV, saves the WAV the page renders offline, then muxes the two with ffmpeg.

    python3 render.py
"""
import http.server
import os
import subprocess
import tempfile
import threading

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "exports", "odd-integral-loop.mp4")
TMP = tempfile.mkdtemp(prefix="odd-integral-")
SILENT = os.path.join(TMP, "silent.mp4")
WAV = os.path.join(TMP, "audio.wav")
PORT = 8771
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

os.makedirs(os.path.dirname(OUT), exist_ok=True)
writer = None
done = threading.Event()


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=HERE, **k)

    def log_message(self, *a):
        pass

    def do_POST(self):
        global writer
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        if self.path.startswith("/frame"):
            img = cv2.imdecode(np.frombuffer(body, np.uint8), cv2.IMREAD_COLOR)
            if writer is None:
                h, w = img.shape[:2]
                writer = cv2.VideoWriter(SILENT, cv2.VideoWriter_fourcc(*"avc1"), 30, (w, h))
            writer.write(img)
            i = int(self.path.split("=")[1])
            if i % 60 == 0:
                print("frame", i, flush=True)
        elif self.path == "/audio":
            with open(WAV, "wb") as f:
                f.write(body)
            print("audio", len(body), "bytes", flush=True)
        elif self.path == "/done":
            done.set()
        self.send_response(204)
        self.end_headers()


server = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
chrome = subprocess.Popen([
    CHROME, "--headless=new", "--disable-gpu", "--force-device-scale-factor=1",
    "--autoplay-policy=no-user-gesture-required",
    "--user-data-dir=" + tempfile.mkdtemp(prefix="odd-render-"),
    "--window-size=1300,1200", f"http://127.0.0.1:{PORT}/index.html?render",
], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    done.wait(timeout=900)
finally:
    chrome.terminate()
    server.shutdown()
    if writer:
        writer.release()
if not done.is_set():
    raise SystemExit("incomplete")
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", SILENT, "-i", WAV,
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
                "-movflags", "+faststart", OUT], check=True)
print("wrote", OUT)
