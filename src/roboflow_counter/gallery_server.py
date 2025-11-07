#!/usr/bin/env python3
"""
Minimal Gallery Webserver
Zeigt die letzten N Bilder aus den letzten X Minuten
für Debug / Larven Highlight Monitor
"""

import os, time, urllib.parse, mimetypes, html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

IMAGE_DIR = Path(os.environ.get("IMAGE_DIR", "/opt/larvacounter/export")).resolve()
PORT = int(os.environ.get("PORT", "8080"))
LIMIT = int(os.environ.get("LIMIT", "20"))        # max Bilder
WINDOW_SEC = int(os.environ.get("WINDOW_SEC", "300"))  # 5 min

IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

def find_recent_images():
    now = time.time()
    cutoff = now - WINDOW_SEC
    files = []

    if not IMAGE_DIR.exists():
        return []

    for p in IMAGE_DIR.rglob("*"):
        if p.is_file() and p.suffix.lower() in IMG_EXTS:
            try: m = p.stat().st_mtime
            except OSError: continue
            if m >= cutoff: files.append((m, p))

    # not enough? then just newest LIMIT
    if len(files) < LIMIT:
        all_files = []
        for p in IMAGE_DIR.rglob("*"):
            if p.is_file() and p.suffix.lower() in IMG_EXTS:
                try: all_files.append((p.stat().st_mtime, p))
                except OSError: continue
        all_files.sort(reverse=True, key=lambda x: x[0])
        return all_files[:LIMIT]

    files.sort(reverse=True, key=lambda x: x[0])
    return files[:LIMIT]


def safe_under(base: Path, path: Path):
    try:
        path.relative_to(base)
        return True
    except:
        return False


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): return  # silence

    def do_GET(self):
        if self.path in ("/", "/index"):
            return self.serve_index()
        if self.path.startswith("/file/"):
            return self.serve_file()
        if self.path == "/health":
            return self.respond(200, b"ok", "text/plain")
        return self.respond(404, b"Not found", "text/plain")

    def serve_index(self):
        items = find_recent_images()
        rows = []
        for mtime, p in items:
            rel = p.relative_to(IMAGE_DIR)
            url = "/file/" + urllib.parse.quote(str(rel).replace("\\", "/"))
            ts = time.strftime("%H:%M:%S", time.localtime(mtime))
            rows.append(f"""
            <div class="card">
                <div class="meta">{html.escape(str(rel))} · {ts}</div>
                <a href="{url}" target="_blank"><img src="{url}"/></a>
            </div>
            """)

        html_body = f"""
<!doctype html><html><head>
<meta http-equiv="refresh" content="10">
<style>
body{{margin:0;font-family:sans-serif;background:#0d1117;color:#c9d1d9}}
header{{padding:10px;background:#161b22;position:sticky;top:0}}
main{{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:10px;padding:10px}}
.card{{background:#161b22;border-radius:8px;overflow:hidden}}
.card img{{width:100%;display:block}}
.meta{{padding:6px;font-size:11px;color:#8b949e}}
</style>
<title>Larvacounter Gallery</title>
</head><body>
<header>Letzte Bilder (≤5min), max {LIMIT}</header>
<main>{''.join(rows) if rows else "<p>Keine Bilder</p>"}</main>
</body></html>
"""
        self.respond(200, html_body.encode(), "text/html")

    def serve_file(self):
        rel = urllib.parse.unquote(self.path[len("/file/"):])
        p = (IMAGE_DIR / rel).resolve()
        if not p.exists() or not p.is_file() or not safe_under(IMAGE_DIR, p):
            return self.respond(404, b"Not found", "text/plain")
        ctype = mimetypes.guess_type(str(p))[0] or "application/octet-stream"
        self.respond(200, p.read_bytes(), ctype)

    def respond(self, code, data, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def run():
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"[gallery] serving {IMAGE_DIR} on :{PORT}")
    srv.serve_forever()


if __name__ == "__main__":
    run()
