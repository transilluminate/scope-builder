#!/usr/bin/env python3
"""Draw the app icon as SVG, then render the PNG sizes with headless Chrome.

    python3 tools/make_icons.py             # writes src/icons/*.svg and *.png
    CHROME=/path/to/chrome python3 tools/make_icons.py

The artwork is a capsule (the medicine) with a tick badge (in scope), centred together on the
square. Each platform crops icons differently, so each gets its own padding:
  icon.svg      browser tabs and the "any" app icon: rounded square, artwork as large as fits
  apple.svg     iOS home screen: the same artwork size on a full square, as iOS rounds the corners itself
  maskable.svg  Android home screen: may be cropped to a circle, so the artwork stays in the
                central 80% safe zone
"""
import os, shutil, subprocess, tempfile
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / 'src' / 'icons'
BG = '#005eb8'
art = f'''<g transform="rotate(-45 218 218)">
    <rect x="53" y="152" width="330" height="132" rx="66" fill="#fff"/>
    <path d="M218 152h99a66 66 0 0 1 0 132h-99z" fill="#9cc6ee"/>
  </g>
  <circle cx="352" cy="352" r="104" fill="{BG}"/>
  <circle cx="352" cy="352" r="84" fill="#009639"/>
  <path d="M312 354l28 28 52-56" fill="none" stroke="#fff" stroke-width="26" stroke-linecap="round" stroke-linejoin="round"/>'''


def svg(scale, rounded):
    t = f'translate(256 256) scale({scale}) translate(-256 -256)'
    corners = ' rx="112"' if rounded else ''
    bg = f'<rect width="512" height="512"{corners} fill="{BG}"/>'
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">\n  {bg}\n  <g transform="{t}">\n  {art}\n  </g>\n</svg>\n'

(OUT / 'icon.svg').write_text(svg(1.12, True))        # browser tab: as big as the rounded square allows
(OUT / 'apple.svg').write_text(svg(1.12, False))      # iOS only rounds the corners, like icon.svg's, so the same size fits
(OUT / 'maskable.svg').write_text(svg(0.92, False))  # Android may crop to a circle: the furthest visible point (about 220 from the centre) stays inside the 80% safe zone (205)

CHROME = os.environ.get('CHROME') or shutil.which('chromium') or shutil.which('google-chrome') or \
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'


def render(svg, size, png):
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / 'r.html'
        page.write_text(f'<html><body style="margin:0"><img src="{(OUT / svg).as_uri()}" width="{size}" height="{size}" style="display:block"></body></html>')
        subprocess.run([CHROME, '--headless', '--disable-gpu', '--hide-scrollbars', '--default-background-color=00000000',
                        f'--user-data-dir={tmp}/profile', f'--window-size={size},{size}', f'--screenshot={OUT / png}', page.as_uri()],
                       check=True, capture_output=True)


for svg, size, png in [('icon.svg', 32, 'favicon-32.png'), ('icon.svg', 192, 'icon-192.png'), ('icon.svg', 512, 'icon-512.png'),
                       ('apple.svg', 180, 'apple-touch-icon.png'),
                       ('maskable.svg', 192, 'maskable-192.png'), ('maskable.svg', 512, 'maskable-512.png')]:
    render(svg, size, png)
print('icons written to', OUT)
