"""Step 3: build output/notebook.html and output/voice_coach.md from analysis/errors.json."""
import json
import sys
from pathlib import Path

from . import coach, config, insights
from .categories import CATEGORIES

TEMPLATE = config.REPO / "notebook" / "template.html"
MARKER = "/*__DATA__*/null"


def notebook_data(data, cfg, live=False):
    return {
        "errors": data["errors"],
        "vocabulary": data.get("vocabulary", []),
        "stats": data.get("stats", []),
        "diagnosis": insights.diagnosis(data),
        "plan": insights.plan(data),
        "categories": {k: [v["name"], v["hint"], v["color"]] for k, v in CATEGORIES.items()},
        "meta": {"explanation_lang": cfg["learner"]["explanation_language"], "live": live},
    }


def render(data, cfg, live=False):
    """live: served by `ui`, which adds the Lessons screen for importing, reviewing and building."""
    html = TEMPLATE.read_text(encoding="utf-8")
    if MARKER not in html:
        sys.exit(f"{TEMPLATE} has no {MARKER} marker")
    payload = json.dumps(notebook_data(data, cfg, live), ensure_ascii=False).replace("</", "<\\/")
    return html.replace(MARKER, payload)


def main(args, cfg):
    source = Path(args.data) if args.data else config.ERRORS
    data = config.read_json(source)
    if data is None:
        sys.exit(f"{source} not found. Run `review` first, or try `build --example`.")
    config.OUTPUT.mkdir(exist_ok=True)
    out = config.OUTPUT / "notebook.html"
    out.write_text(render(data, cfg), encoding="utf-8")
    (config.OUTPUT / "voice_coach.md").write_text(coach.render(data, cfg), encoding="utf-8")
    print(f"Wrote {out} ({len(data['errors'])} errors) and output/voice_coach.md. Open the HTML file in a browser.")
