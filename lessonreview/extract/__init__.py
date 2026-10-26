"""Step 1: copy lessons from Cambly and Preply into raw/*.md, resuming from manifest.json.

A real Chrome window opens with its own profile (.browser-profile/). The first time, log in to each
platform in that window; the session is kept for later runs. Alternatively, attach to a Chrome you
started yourself with --remote-debugging-port (config: browser.cdp_url).
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

from .. import config, rawfile
from . import parse

JS = Path(__file__).parent / "js"
CAMBLY_LIST = "https://www.cambly.com/en/student/progress/past-lessons"
CAMBLY_LESSON = "https://www.cambly.com/en/student/progress/past-lesson?lessonV2Id={id}"
PREPLY_LIST = "https://preply.com/en/lessons"
PREPLY_LESSON = "https://preply.com/edu/lesson-insights/{id}"


def js(name):
    """The function source, without its leading comment (Playwright detects functions by their first token)."""
    lines = (JS / name).read_text(encoding="utf-8").splitlines()
    return "\n".join(l for l in lines if not l.startswith("//"))


def load_manifest():
    return config.read_json(config.MANIFEST, {"lessons": []})


def in_period(day, cfg):
    return cfg["period"]["from"] <= day <= cfg["period"]["to"]


def wait_for_login(page, url, check, platform):
    page.goto(url)
    page.wait_for_load_state("domcontentloaded")
    if check():
        return
    print(f"\nLog in to {platform} in the browser window that just opened, then press Enter here.")
    input()
    page.goto(url)
    page.wait_for_load_state("domcontentloaded")
    if not check():
        sys.exit(f"Still not logged in to {platform}. Run the command again after logging in.")


# --- Cambly -------------------------------------------------------------------

def cambly_list(page, cfg):
    state = {}

    def check():
        page.wait_for_timeout(1500)
        state.update(page.evaluate(js("cambly_list.js")))
        return "error" not in state

    wait_for_login(page, CAMBLY_LIST, check, "Cambly")
    lessons = []
    for l in state["lessons"]:
        start = l["start"]
        dt = (datetime.fromtimestamp(start / 1000, timezone.utc) if isinstance(start, (int, float))
              else datetime.fromisoformat(str(start).replace("Z", "+00:00"))).astimezone()
        if in_period(dt.date().isoformat(), cfg):
            lessons.append({"source": "cambly", "id": l["id"], "date": dt.date().isoformat(),
                            "time": dt.strftime("%H:%M"), "minutes": l["minutes"]})
    return state["userId"], lessons


def cambly_lesson(page, lesson, user_id):
    page.goto(CAMBLY_LESSON.format(id=lesson["id"]))
    result = page.evaluate(js("cambly_lesson.js"), user_id)
    if "error" in result:
        raise RuntimeError(result["error"])
    lines = result["feedbackLines"]
    if parse.cambly_pending(lines):
        raise RuntimeError("feedback still being prepared by Cambly; try again later")
    meta = {"source": "cambly", "id": lesson["id"], "date": lesson["date"], "time": lesson["time"],
            "duration_min": lesson.get("minutes"), **parse.cambly_header(lines)}
    transcript = [(s, t) for s, t in result["rows"]]
    return meta, parse.cambly_feedback(lines), [], transcript


# --- Preply -------------------------------------------------------------------

def preply_list(page, cfg):
    nodes = []

    def on_response(resp):
        if "CurrentUserPastLessons" in resp.url:
            try:
                nodes.extend(resp.json()["data"]["currentUser"]["client"]["pastLessons"]["nodes"])
            except Exception:
                pass

    page.on("response", on_response)

    def check():
        page.wait_for_timeout(3000)
        return "/login" not in page.url and page.get_by_text("Past lessons", exact=False).count() > 0

    wait_for_login(page, PREPLY_LIST, check, "Preply")
    more = page.get_by_role("button", name="More past lessons")
    for _ in range(50):  # load older pages until the period start is covered
        oldest = min((n["datetime"][:10] for n in nodes), default="9999")
        if oldest < cfg["period"]["from"] or more.count() == 0:
            break
        more.first.click()
        page.wait_for_timeout(2500)
    page.remove_listener("response", on_response)

    lessons, seen = [], set()
    for n in nodes:
        dt = datetime.fromisoformat(n["datetime"].replace("Z", "+00:00")).astimezone()
        if n["id"] in seen or not in_period(dt.date().isoformat(), cfg):
            continue
        seen.add(n["id"])
        tutor = ((n.get("tutor") or {}).get("user") or {}).get("firstName", "")
        lessons.append({"source": "preply", "id": str(n["id"]), "date": dt.date().isoformat(),
                        "time": dt.strftime("%H:%M"), "minutes": n.get("duration"), "tutor": tutor})
    return lessons


def preply_lesson(page, lesson):
    page.goto(PREPLY_LESSON.format(id=lesson["id"]))
    result = page.evaluate(js("preply_lesson.js"))
    if "error" in result:
        raise RuntimeError(result["error"])
    lines = result["lines"]
    meta = {"source": "preply", "id": lesson["id"], "date": lesson["date"], "time": lesson["time"],
            "tutor": lesson.get("tutor"), "duration_min": lesson.get("minutes"), **parse.preply_header(lines)}
    return meta, parse.preply_feedback(lines), parse.preply_vocabulary(lines), []


# --- Orchestration ------------------------------------------------------------

def open_browser(p, cfg):
    b = cfg["browser"]
    if b.get("cdp_url"):
        browser = p.chromium.connect_over_cdp(b["cdp_url"])
        return browser.contexts[0], browser
    kwargs = {"headless": False, "viewport": {"width": 1280, "height": 900}}
    if b.get("channel"):
        kwargs["channel"] = b["channel"]
    ctx = p.chromium.launch_persistent_context(str(config.ROOT / b["profile_dir"]), **kwargs)
    return ctx, ctx


def run(args, cfg):
    from playwright.sync_api import Error as PlaywrightError, sync_playwright

    manifest = load_manifest()
    known = {(l["source"], l["id"]): l for l in manifest["lessons"]}
    platforms = [args.platform] if args.platform else cfg["platforms"]
    config.RAW.mkdir(exist_ok=True)
    done = 0

    with sync_playwright() as p:
        ctx, closer = open_browser(p, cfg)
        page = ctx.new_page()
        try:
            for platform in platforms:
                if platform == "cambly":
                    user_id, listed = cambly_list(page, cfg)
                else:
                    user_id, listed = None, preply_list(page, cfg)
                for l in listed:
                    if (l["source"], l["id"]) not in known:
                        known[l["source"], l["id"]] = {**l, "status": "pending"}
                        manifest["lessons"].append(known[l["source"], l["id"]])
                config.write_json(config.MANIFEST, manifest)
                todo = sorted((l for l in manifest["lessons"] if l["source"] == platform and l["status"] != "done"),
                              key=lambda l: l["date"])
                print(f"{platform}: {len(listed)} lessons in the period, {len(todo)} to extract")
                for l in todo:
                    if args.limit and done >= args.limit:
                        break
                    try:
                        meta, feedback, vocab, transcript = (cambly_lesson(page, l, user_id) if platform == "cambly"
                                                             else preply_lesson(page, l))
                    except (RuntimeError, PlaywrightError) as e:
                        l["status"], l["note"] = "pending", str(e)[:200]
                        print(f"  {l['date']}: skipped ({str(e)[:120]})")
                        config.write_json(config.MANIFEST, manifest)
                        continue
                    existing = {f.name for f in config.RAW.glob("*.md")}
                    name = l.get("file") or rawfile.filename(platform, l["date"], existing)
                    (config.RAW / name).write_text(rawfile.render(meta, feedback, vocab, transcript), encoding="utf-8")
                    l.update(status="done", file=name, tutor=meta.get("tutor") or l.get("tutor"))
                    l.pop("note", None)
                    config.write_json(config.MANIFEST, manifest)  # save after every lesson
                    done += 1
                    print(f"  {l['date']}: {name} ({len(feedback)} corrections, {len(transcript)} transcript lines)")
        finally:
            closer.close()
    left = sum(1 for l in manifest["lessons"] if l["status"] != "done")
    print(f"Extracted {done} lessons. {left} still pending" + (" (run again to continue)." if left else "."))
