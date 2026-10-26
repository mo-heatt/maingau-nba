"""Turn the static Vite build into one self-contained HTML page for the artifact."""
import base64, re, sys, pathlib
dist, snap, out = map(pathlib.Path, sys.argv[1:4])
html = (dist / "index.html").read_text()
css_href = re.search(r'<link rel="stylesheet"[^>]*href="([^"]+)"[^>]*>', html)
js_src = re.search(r'<script type="module"[^>]*src="([^"]+)"[^>]*></script>', html)
css = (dist / css_href.group(1)).read_text()
for font in ("rondelle-regular", "rondelle-bold"):
    data = base64.b64encode((dist / "fonts" / f"{font}.woff2").read_bytes()).decode()
    css = re.sub(r"url\(['\"]?[./]*fonts/" + font + r"\.woff2['\"]?\)", f"url(data:font/woff2;base64,{data})", css)
assert "fonts/rondelle" not in css, "font not inlined"
js = (dist / js_src.group(1)).read_text().replace("</script", "<\\/script")
snap_b64 = base64.b64encode(snap.read_bytes()).decode()
page = (
    '<!doctype html><html lang="en"><head><meta charset="utf-8">\n'
    '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
    "<title>MAINGAU Next Best Action</title>\n"
    '<meta name="theme-color" content="#002657">\n'
    f"<style>{css}</style></head><body>\n"
    '<div id="root"></div>\n'
    f'<script>window.__SNAP_GZ="{snap_b64}";</script>\n'
    f'<script type="module">{js}</script></body></html>\n'
)
out.write_text(page)
print(out, round(len(page) / 1e6, 2), "MB")
