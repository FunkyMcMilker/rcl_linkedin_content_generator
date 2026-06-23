import os
from io import BytesIO

from flask import Flask, request, send_file, abort, jsonify
from jinja2 import Environment, FileSystemLoader, select_autoescape
from playwright.sync_api import sync_playwright

app = Flask(__name__)

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")
env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=select_autoescape(["html", "j2"]),
)

# Optional shared secret. If set in Railway, the Make HTTP module must send
# Authorization: Bearer <RENDER_TOKEN>. If unset, the endpoint is open.
RENDER_TOKEN = os.environ.get("RENDER_TOKEN")


@app.get("/")
def health():
    return jsonify(status="ok")


@app.post("/render")
def render():
    if RENDER_TOKEN and request.headers.get("Authorization", "") != f"Bearer {RENDER_TOKEN}":
        abort(401)

    data = request.get_json(force=True, silent=True) or {}
    if not data.get("hero_image_url") or not (data.get("hook") or data.get("stat_value")):
        abort(400, "hero_image_url and either hook or stat_value are required")

    html = env.get_template("linkedin_card.html.j2").render(**data)

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        page = browser.new_page(
            viewport={"width": 1080, "height": 1350},
            device_scale_factor=2,  # crisp 2160x2700 PNG; set to 1 for exactly 1080x1350
        )
        # networkidle lets Google Fonts + the data-URI hero settle; fonts.ready is the belt-and-braces.
        page.set_content(html, wait_until="networkidle")
        page.evaluate("async () => { await document.fonts.ready; }")
        png = page.screenshot(type="png")  # clipped to viewport
        browser.close()

    return send_file(BytesIO(png), mimetype="image/png", download_name="linkedin_card.png")


if __name__ == "__main__":
    # Local dev only. In Railway, gunicorn (see Dockerfile CMD) serves the app.
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
