#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gallery Webserver (evenly spaced)
- zeigt N Bilder gleichmäßig verteilt über die letzten WINDOW_SEC Sekunden
- Slot-Breite = WINDOW_SEC / N (Standard: 300 / 20 = 15 s)
- Fallback: falls Slot leer, bleibt Lücke; danach optional mit übrigen Bildern auffüllen
- /zip liefert ein ZIP der aktuell selektierten Bilder

ENV:
  IMAGE_DIR   (default: /opt/larvacounter/export)
  PORT        (default: 8080)
  LIMIT       (default: 20)        # N
  WINDOW_SEC  (default: 300)       # 5 min
  REFRESH_SEC (default: 10)
  TITLE       (default: 'Letzte Bilder (≤5min, gleichmäßig)')
  FILL_GAPS   (default: 1)         # 1: Lücken nachträglich mit neuesten füllen, 0: Lücken zulassen
"""

import os, io, time, urllib.parse, mimetypes, html, zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

IMAGE_DIR   = Path(os.environ.get("IMAGE_DIR", "/opt/larvacounter/export")).resolve()
PORT        = int(os.environ.get("PORT", "8080"))
LIMIT       = int(os.environ.get("LIMIT", "20"))
WINDOW_SEC  = int(os.environ.get("WINDOW_SEC", "300"))
REFRESH_SEC = int(os.environ.get("REFRESH_SEC", "10"))
TITLE       = os.environ.get("TITLE", "Letzte Bilder (≤5min, gleichmäßig)")
FILL_GAPS   = int(os.environ.get("FILL_GAPS", "1"))

IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

def _scan(dirpath: Path):
    """Scant rekursiv Bilddateien (mtime, path)."""
    items = []
    if not dirpath.exists():
        return items
    for p in dirpath.rglob("*"):
        if p.is_file() and p.suffix.lower() in IMG_EXTS:
            try:
                items.append((p.stat().st_mtime, p))
            except OSError:
                continue
    return items

def select_evenly_spaced(items, now=None, window=300, count=20):
    """
    items: List[(mtime, Path)] beliebig alt
    Auswahl: gleichmäßig über [now-window, now], 'count' Slots
    Für jeden Slot wird das Bild mit minimaler |mtime - slot_center| gewählt (ohne Duplikate).
    """
    if now is None:
        now = time.time()
    if count <= 0 or window <= 0:
        return []

    start = now - window
    slot = float(window) / float(count)  # typ. 15 s
    # Slot-Center (damit früh & spät halbgewichtet werden)
    centers = [start + (i + 0.5) * slot for i in range(count)]

    # Nur Kandidaten im Fenster betrachten
    in_window = [(m, p) for (m, p) in items if start <= m <= now]
    # Für Lücken-Fallback ggf. alle sortiert parat halten
    all_sorted = sorted(items, key=lambda x: x[0], reverse=True)
    used = set()
    selection = [None] * count

    # Für jede Center-Zeit das nächstliegende Bild wählen
    for i, c in enumerate(centers):
        best = None
        best_dt = None
        for (m, p) in in_window:
            if p in used:
                continue
            dt = abs(m - c)
            # bevorzugt innerhalb ± slot/2; wenn keines da, nehmen wir trotzdem das minimal dt im Fenster
            if best_dt is None or dt < best_dt:
                best_dt = dt
                best = (m, p)
        if best is not None:
            selection[i] = best
            used.add(best[1])

    # Optional: Lücken mit übrigen neueren Bildern auffüllen (damit man immer bis zu N sieht)
    if FILL_GAPS:
        for i in range(count):
            if selection[i] is None:
                for (m, p) in all_sorted:
                    if p not in used:
                        selection[i] = (m, p)
                        used.add(p)
                        break

    # Sortierung: neueste zuerst (UI zeigt Grid; du kannst hier auch nach Zeit auf-/absteigend sortieren)
    out = [x for x in selection if x is not None]
    out.sort(key=lambda x: x[0], reverse=True)
    return out[:count]

def find_images_even():
    now = time.time()
    items = _scan(IMAGE_DIR)
    return select_evenly_spaced(items, now=now, window=WINDOW_SEC, count=LIMIT)

def safe_under(base: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(base)
        return True
    except ValueError:
        return False

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):  # silence
        return

    def do_GET(self):
        if self.path in ("/", "/index"):
            return self.serve_index()
        if self.path.startswith("/file/"):
            return self.serve_file()
        if self.path == "/zip":
            return self.serve_zip()
        if self.path == "/health":
            return self.respond(200, b"ok", "text/plain; charset=utf-8")
        return self.respond(404, b"Not found", "text/plain; charset=utf-8")

    def serve_index(self):
        items = find_images_even()
        rows = []
        for mtime, p in items:
            rel = p.relative_to(IMAGE_DIR)
            url = "/file/" + urllib.parse.quote(str(rel).replace("\\", "/"))
            ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mtime))
            rows.append(f"""
              <div class="card">
                <div class="meta">{html.escape(str(rel))} · {ts}</div>
                <a href="{url}" target="_blank" rel="noopener">
                  <img loading="lazy" src="{url}" />
                </a>
              </div>
            """)
        count = len(items)
        body = f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8" />
  <meta http-equiv="refresh" content="{REFRESH_SEC}">
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(TITLE)} – {LIMIT} Slots</title>
  <style>
    :root {{ --bg:#0b0d10; --fg:#e8eef2; --muted:#9aa7b2; --card:#151a20; --accent:#5aa9e6; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:var(--bg); color:var(--fg); font-family:system-ui,-apple-system,Segoe UI,Roboto,Inter,Arial,sans-serif; }}
    header {{ position:sticky; top:0; background:rgba(11,13,16,.9); backdrop-filter:blur(8px);
             border-bottom:1px solid #222a33; padding:12px 16px; z-index:10; display:flex; gap:10px; align-items:center; flex-wrap:wrap; }}
    h1 {{ margin:0; font-size:18px; }}
    .pill {{ padding:4px 8px; border:1px solid #2b3541; border-radius:999px; color:var(--muted); }}
    .btn {{ padding:6px 10px; border-radius:10px; background:var(--accent); color:#001018; text-decoration:none; font-weight:600; }}
    main {{ padding:16px; display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:14px; }}
    .card {{ background:var(--card); border:1px solid #222a33; border-radius:14px; overflow:hidden; box-shadow:0 2px 12px rgba(0,0,0,.2); }}
    .card img {{ display:block; width:100%; height:auto; }}
    .meta {{ font-size:12px; color:var(--muted); padding:8px 10px; border-bottom:1px solid #222a33; }}
    footer {{ color:var(--muted); font-size:12px; padding:10px 16px; }}
    a {{ color:var(--accent); text-decoration:none; }}
  </style>
</head>
<body>
  <header>
    <h1>{html.escape(TITLE)}</h1>
    <span class="pill">Slots: {LIMIT} · Fenster: {WINDOW_SEC}s (≈ {WINDOW_SEC//LIMIT if LIMIT else 0}s / Slot)</span>
    <span class="pill">Verzeichnis: {html.escape(str(IMAGE_DIR))}</span>
    <a class="pill" href="/health">health</a>
    <a class="btn" href="/zip" download>{LIMIT}&nbsp;Bilder&nbsp;als&nbsp;ZIP</a>
  </header>
  <main>
    {''.join(rows) if rows else '<p>Keine Bilder gefunden.</p>'}
  </main>
  <footer>Aktualisiert: {time.strftime("%Y-%m-%d %H:%M:%S")}</footer>
</body>
</html>"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def serve_file(self):
        rel = urllib.parse.unquote(self.path[len("/file/"):])
        target = (IMAGE_DIR / rel).resolve()
        if not safe_under(IMAGE_DIR, target) or not target.exists() or not target.is_file():
            return self.respond(404, b"Not found", "text/plain; charset=utf-8")
        ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        try:
            with open(target, "rb") as f:
                data = f.read()
        except OSError:
            return self.respond(404, b"Not found", "text/plain; charset=utf-8")
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "max-age=60, public")
        self.end_headers()
        self.wfile.write(data)

    def serve_zip(self):
        items = find_images_even()
        if not items:
            return self.respond(404, b"No images", "text/plain; charset=utf-8")
        buf = io.BytesIO()
        ts = time.strftime("%Y%m%d_%H%M%S")
        with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as z:
            for mtime, p in items:
                rel = p.relative_to(IMAGE_DIR)
                z.write(p, arcname=str(rel))
        data = buf.getvalue()
        fname = f"gallery_{ts}.zip"
        self.send_response(200)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Disposition", f'attachment; filename="{fname}"')
        self.end_headers()
        self.wfile.write(data)

    def respond(self, code, data: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

def run():
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"[gallery] serving {IMAGE_DIR} on :{PORT} (limit={LIMIT}, window={WINDOW_SEC}s, slot≈{WINDOW_SEC/max(LIMIT,1):.1f}s)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    run()
