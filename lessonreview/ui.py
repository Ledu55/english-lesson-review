"""Local web app: python -m lessonreview ui

Serves the practice notebook with an extra Lessons screen, where you paste a lesson's page text to import it,
see every lesson's status, and run review and build. The notebook is rendered from analysis/errors.json on
every load, so it always shows the latest reviews. The server listens on 127.0.0.1 only and serves one request at a time,
so commands never overlap. Automated extraction is the exception: it runs in a background thread, and only when the
request says the user accepted the risk to their account (the page asks every time).
"""
import contextlib
import importlib.util
import io
import json
import os
import sys
import threading
import webbrowser
from datetime import datetime
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import SimpleNamespace

from . import config

EMPTY = {"errors": [], "vocabulary": [], "stats": []}
OUTPUT_FILES = {"notebook.html": "text/html", "voice_coach.md": "text/markdown"}
COMMANDS = ("import", "review-offline", "review-api", "build")
LOGIN_WAIT = 600  # seconds the extractor waits for the user to log in, in the browser window it opens
JOB = {"running": False, "ok": None, "log": ""}


class _JobLog(io.TextIOBase):
    def write(self, s):
        JOB["log"] += s
        return len(s)


def state(cfg):
    from . import review
    manifest = config.read_json(config.MANIFEST, {"lessons": []})["lessons"]
    reviewed = {p.stem for p in config.REVIEWS.glob("*.json")}
    lessons = [{**{k: l.get(k) for k in ("source", "date", "tutor", "file", "method", "status")},
                "reviewed": bool(l.get("file")) and l["file"].removesuffix(".md") in reviewed}
               for l in manifest]
    lessons.sort(key=lambda l: (l["date"] or "", l["file"] or ""), reverse=True)
    from . import importer
    from .extract import HISTORY
    return {
        "period": cfg["period"],
        "lessons": lessons,
        "pending": len(review.pending()) if config.RAW.exists() else 0,
        "inbox": len(list(importer.INBOX.glob("*.txt"))) if importer.INBOX.exists() else 0,
        "outputs": [n for n in OUTPUT_FILES if (config.OUTPUT / n).exists()],
        "history": HISTORY,
        "platforms": cfg["platforms"],
        "extract_available": importlib.util.find_spec("playwright") is not None,
        "extracting": JOB["running"],
        "api": api_status(),
        "mcp": mcp_status(),
    }


def api_status():
    """Which provider reviews use and where each key comes from, never the keys themselves."""
    from . import providers
    data = config.read_json(config.SECRETS, {}) or {}
    key, other = data.get("anthropic_api_key"), data.get("openai")
    return {
        "provider": "openai" if providers.settings() else "anthropic",
        "anthropic": {"source": "saved", "hint": "…" + key[-4:]} if key else
                     {"source": "env"} if os.environ.get("ANTHROPIC_API_KEY") else {"source": None},
        "openai": {k: other.get(k) for k in ("preset", "base_url", "model")} | {
                  "hint": "…" + other["api_key"][-4:] if other.get("api_key") else None} if other else None,
        "presets": {k: {"name": v[0], "base_url": v[1], "model": v[2], "key": v[3], "keys_url": v[4]}
                    for k, v in providers.PRESETS.items()},
    }


def _save_secrets(**changes):
    data = config.read_json(config.SECRETS, {}) or {}
    data.update(changes)
    data = {k: v for k, v in data.items() if v is not None}
    if data.keys() - {"provider"}:
        config.write_json(config.SECRETS, data)
    else:
        config.SECRETS.unlink(missing_ok=True)


def save_api_key(key):
    """Check an Anthropic key with one free request (listing models), keep it in secrets.json and review with
    Anthropic again. An empty key removes it."""
    key = (key or "").strip()
    if not key:
        _save_secrets(anthropic_api_key=None)
        return {"ok": True, "message": "Anthropic API key removed."}
    if not key.startswith("sk-ant-"):
        return {"ok": False, "message": "That doesn't look like an Anthropic API key (they start with sk-ant-)."}
    import anthropic
    try:
        anthropic.Anthropic(api_key=key).models.list(limit=1)
    except anthropic.AuthenticationError:
        return {"ok": False, "message": "Anthropic rejected this key. Check it at console.anthropic.com."}
    except anthropic.APIError as e:
        return {"ok": False, "message": f"Couldn't check the key: {e}"}
    _save_secrets(anthropic_api_key=key, provider="anthropic")
    return {"ok": True, "message": "API key saved and working. \"Review with API\" will use Claude."}


def save_provider(body):
    """Use another provider: {preset, base_url, model, key}. A blank key keeps the saved one for the same server.
    {"use": "anthropic" | "openai"} switches between Claude and the saved provider; {"remove": true} forgets it."""
    from . import providers
    if body.get("use") == "anthropic":
        _save_secrets(provider="anthropic")
        return {"ok": True, "message": "Reviews will use Claude again."}
    if body.get("use") == "openai":
        if not (config.read_json(config.SECRETS, {}) or {}).get("openai"):
            return {"ok": False, "message": "Connect a provider first."}
        _save_secrets(provider="openai")
        return {"ok": True, "message": "Reviews will use the saved provider."}
    if body.get("remove"):
        _save_secrets(provider="anthropic", openai=None)
        return {"ok": True, "message": "Provider removed. Reviews will use Claude."}
    preset = body.get("preset") if body.get("preset") in providers.PRESETS else "custom"
    base_url = (body.get("base_url") or providers.PRESETS[preset][1]).strip().rstrip("/")
    model = (body.get("model") or "").strip()
    if not base_url.startswith(("http://", "https://")) or not model:
        return {"ok": False, "message": "Fill in the server URL and the model name."}
    saved = (config.read_json(config.SECRETS, {}) or {}).get("openai") or {}
    key = (body.get("key") or "").strip() or (saved.get("api_key") if saved.get("base_url") == base_url else None)
    if providers.PRESETS[preset][3] and not key:
        return {"ok": False, "message": f"{providers.PRESETS[preset][0]} needs an API key."}
    s = {"preset": preset, "base_url": base_url, "model": model, "api_key": key}
    try:
        providers.check(s)
    except providers.ProviderError as e:
        return {"ok": False, "message": f"Couldn't connect: {e}"}
    _save_secrets(provider="openai", openai=s)
    return {"ok": True, "message": f"Connected. \"Review with API\" will use {model} on {providers.PRESETS[preset][0]}. "
                                   "Your lesson transcripts will be sent to that provider."}


def desktop_config_path():
    if sys.platform == "win32":  # the Microsoft Store version keeps its config inside its package folder
        store = sorted(Path(os.environ.get("LOCALAPPDATA", "")).glob("Packages/Claude_*/LocalCache/Roaming/Claude"))
        if store:
            return store[0] / "claude_desktop_config.json"
    base = os.environ.get("APPDATA") if sys.platform == "win32" else (
        os.path.expanduser("~/Library/Application Support") if sys.platform == "darwin"
        else os.path.expanduser("~/.config"))
    return Path(base) / "Claude" / "claude_desktop_config.json"


def mcp_entry():
    """How Claude Desktop starts the review server: this Python, this project, from any working directory."""
    return {"command": sys.executable, "args": ["-m", "lessonreview.mcp_server"],
            "env": {"LESSONREVIEW_HOME": str(config.ROOT), "PYTHONPATH": str(config.REPO)}}


def mcp_status():
    path = desktop_config_path()
    try:
        servers = (config.read_json(path, {}) or {}).get("mcpServers", {})
    except ValueError:
        servers = {}
    return {
        "installed": importlib.util.find_spec("mcp") is not None,
        "claude_code": (config.REPO / ".mcp.json").exists(),
        "desktop_app": path.parent.exists(),
        "desktop_connected": "english-lesson-review" in servers,
        "desktop_config": str(path),
        "entry": {"mcpServers": {"english-lesson-review": mcp_entry()}},
    }


def connect_desktop():
    """Add the review server to Claude Desktop's config, keeping everything else in it (and a .bak copy)."""
    path = desktop_config_path()
    if not path.parent.exists():
        return {"ok": False, "message": f"Claude Desktop isn't installed here ({path.parent} not found)."}
    try:
        data = config.read_json(path, {}) or {}
    except ValueError:
        return {"ok": False, "message": f"{path} isn't valid JSON; fix it or add the snippet by hand."}
    if path.exists():
        path.with_suffix(".json.bak").write_bytes(path.read_bytes())
    data.setdefault("mcpServers", {})["english-lesson-review"] = mcp_entry()
    config.write_json(path, data)
    return {"ok": True, "message": "Added to Claude Desktop. Quit it completely (also from the tray) and open it "
                                   "again, then ask: \"Review all pending lessons with the english-lesson-review tools, "
                                   "then build the notebook.\""}


def paste_import(text, cfg, platform=None, day=None):
    """Save pasted page text in inbox/ and import it. The inbox copy is kept only if the import worked."""
    from . import importer
    if not text.strip():
        return {"ok": False, "message": "Nothing pasted."}
    importer.INBOX.mkdir(exist_ok=True)
    config.RAW.mkdir(exist_ok=True)
    path = importer.INBOX / f"pasted_{datetime.now():%Y%m%d_%H%M%S_%f}.txt"
    path.write_text(text, encoding="utf-8")
    manifest = config.read_json(config.MANIFEST, {"lessons": []})
    name, msg = importer.import_file(path, cfg, manifest, platform or None, day or None)
    if not name:
        path.unlink()
        return {"ok": False, "message": f"Skipped: {msg}."}
    config.write_json(config.MANIFEST, manifest)
    return {"ok": True, "message": f"Imported {name} ({msg})."}


def run_command(cmd, cfg):
    """Run a pipeline step, returning what it printed. Steps report problems with sys.exit(message)."""
    from . import build, importer, review
    out, ok = io.StringIO(), True
    with contextlib.redirect_stdout(out):
        try:
            if cmd == "import":
                importer.run(SimpleNamespace(files=[], platform=None, date=None), cfg)
            elif cmd in ("review-offline", "review-api"):
                review.main(SimpleNamespace(offline=cmd == "review-offline", limit=None), cfg)
            elif cmd == "build":
                build.main(SimpleNamespace(data=None), cfg)
        except SystemExit as e:
            ok = e.code in (None, 0)
            if isinstance(e.code, str):
                print(e.code)
        except Exception as e:  # show the error on the page instead of dropping the connection
            ok = False
            print(f"{type(e).__name__}: {e}")
    return {"ok": ok, "message": out.getvalue().strip() or "Done."}


def start_extract(body, cfg):
    """Start the automated extractor in the background. Only the user can accept the terms risk, on the page."""
    if body.get("accept_terms_risk") is not True:
        return {"ok": False, "message": "Not started: tick the box to confirm you accept the risk to your account."}
    if JOB["running"]:
        return {"ok": False, "message": "Extraction is already running."}
    if importlib.util.find_spec("playwright") is None:
        return {"ok": False, "message": "Playwright is not installed. Run: pip install playwright"}
    platform = body.get("platform") if body.get("platform") in ("cambly", "preply") else None
    limit = body.get("limit") if isinstance(body.get("limit"), int) and body["limit"] > 0 else None
    JOB.update(running=True, ok=None, log="")
    threading.Thread(target=_extract, args=(SimpleNamespace(platform=platform, limit=limit), cfg), daemon=True).start()
    return {"ok": True, "message": "Started."}


def _extract(args, cfg):
    from . import extract
    extract.LOGIN_WAIT, ok = LOGIN_WAIT, True
    with contextlib.redirect_stdout(_JobLog()):
        try:
            extract.run(args, cfg)
        except SystemExit as e:
            ok = e.code in (None, 0)
            if isinstance(e.code, str):
                print(e.code)
        except Exception as e:
            ok = False
            print(f"{type(e).__name__}: {e}")
    JOB.update(running=False, ok=ok)


class Handler(BaseHTTPRequestHandler):
    cfg = None

    def _send(self, body, ctype="application/json", status=200):
        data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", f"{ctype}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _local_host(self):
        # Refuse other Host names so a web page can't reach this server through DNS rebinding.
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
        return host in ("127.0.0.1", "localhost")

    def do_GET(self):
        if not self._local_host():
            return self._send({"error": "forbidden"}, status=403)
        path = self.path.split("?")[0]
        if path == "/":
            from . import build
            data = config.read_json(config.ERRORS, EMPTY)
            return self._send(build.render(data, self.cfg, live=True).encode("utf-8"), "text/html")
        if path == "/api/state":
            return self._send(state(self.cfg))
        if path == "/api/extract":
            return self._send(JOB)
        name = path.removeprefix("/output/")
        if name in OUTPUT_FILES and (config.OUTPUT / name).exists():
            return self._send((config.OUTPUT / name).read_bytes(), OUTPUT_FILES[name])
        self._send({"error": "not found"}, status=404)

    def do_POST(self):
        # JSON only: a cross-site form can't send it without the browser asking this server first.
        if not self._local_host() or not self.headers.get("Content-Type", "").startswith("application/json"):
            return self._send({"error": "forbidden"}, status=403)
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        except ValueError:
            return self._send({"error": "invalid JSON"}, status=400)
        if self.path == "/api/extract":
            return self._send(start_extract(body, self.cfg))
        if JOB["running"]:
            return self._send({"ok": False, "message": "Wait until the extraction finishes."})
        if self.path == "/api/key":
            return self._send(save_api_key(body.get("key")))
        if self.path == "/api/provider":
            return self._send(save_provider(body))
        if self.path == "/api/mcp/desktop":
            return self._send(connect_desktop())
        if self.path == "/api/import":
            return self._send(paste_import(body.get("text", ""), self.cfg, body.get("platform"), body.get("date")))
        cmd = self.path.removeprefix("/api/run/")
        if cmd in COMMANDS:
            return self._send(run_command(cmd, self.cfg))
        self._send({"error": "not found"}, status=404)

    def log_message(self, *args):
        pass


def run(args, cfg):
    Handler.cfg = cfg
    server = HTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://localhost:{args.port}/"
    print(f"Lesson review is open at {url} (Ctrl+C to stop)")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopped.")
