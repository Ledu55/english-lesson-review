"""Configuration and project paths.

Everything is resolved against the project root: the current directory, or LESSONREVIEW_HOME.
"""
import json
import os
import shutil
from pathlib import Path

ROOT = Path(os.environ.get("LESSONREVIEW_HOME") or Path.cwd()).resolve()
PACKAGE = Path(__file__).resolve().parent
REPO = PACKAGE.parent

RAW = ROOT / "raw"
ANALYSIS = ROOT / "analysis"
REVIEWS = ANALYSIS / "reviews"
ERRORS = ANALYSIS / "errors.json"
OUTPUT = ROOT / "output"
MANIFEST = ROOT / "manifest.json"
CONFIG = ROOT / "config.json"
SECRETS = ROOT / "secrets.json"  # API key saved from the `ui` page; git-ignored

DEFAULTS = {
    "period": {"from": "2000-01-01", "to": "2100-01-01"},
    "platforms": ["cambly", "preply"],
    "learner": {
        "native_language": "Portuguese",
        "explanation_language": "en",
        "level": "B2",
        "background": "",
    },
    "review": {"model": "claude-sonnet-5-5", "max_tokens": 16000},
    "browser": {"channel": "chrome", "profile_dir": ".browser-profile", "cdp_url": None},
}


def _merge(base, extra):
    out = dict(base)
    for k, v in (extra or {}).items():
        out[k] = _merge(base[k], v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return out


def load():
    """Read config.json, creating it from config.example.json on first use."""
    if not CONFIG.exists():
        example = REPO / "config.example.json"
        if example.exists():
            shutil.copy(example, CONFIG)
            print(f"Created {CONFIG.name} from config.example.json. Edit it to set your period and language.")
    data = json.loads(CONFIG.read_text(encoding="utf-8")) if CONFIG.exists() else {}
    return _merge(DEFAULTS, data)


def api_key():
    """The Anthropic API key saved from the `ui` page, or None to let the SDK use ANTHROPIC_API_KEY / `ant auth login`."""
    return (read_json(SECRETS, {}) or {}).get("anthropic_api_key") or None


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
