"""Tests for the parts that run without a browser or an API key.

The page-text fixtures mirror the structure of real Cambly and Preply pages (Portuguese interface for Cambly,
mixed for Preply), with invented sentences.
"""
import json

import pytest

from lessonreview import aggregate, build, config, insights, rawfile, review, schema
from lessonreview.extract import parse

CAMBLY_LINES = [
    "Histórico de aulas", "FEEDBACK", "TRANSCRIÇÃO", "SLIDES", "CHAT", "Alex", "8 de setembro de 2026",
    "Porcentagem de conversação", "65%", "Palavras por minuto", "131", "Palavras exclusivas", "402", "30 minutos",
    "Gramática", "O QUE VOCÊ ESTÁ FAZENDO BEM:", "You used connectors well.", "EXPLICAÇÃO:", "Like 'even though'.",
    "Isso é inútil ou incorreto",
    "Gramática", "VOCÊ DISSE:", "I have less things to do", "SUGESTÃO:", "I have fewer things to do",
    "EXPLICAÇÃO:", "'Things' is countable.", "Isso é inútil ou incorreto",
    "Vocabulário", "VOCÊ DISSE:", "every section in the app", "SUGESTÃO:", "every session in the app",
    "EXPLICAÇÃO:", "A session is a period of use.",
]

PREPLY_LINES = [
    "Inglês, Sam", "24 de ago., 18:30 – 19:20", "Tempo de conversação", "Você", "10", "Sam",
    "27 min (57%)", "20 min (43%)", "Tema do dia", "Handling tough questions",
    "Você disse", "...The family dinner, we always argue.", "Correção", "At family dinner, we always argue.",
    "Articles", "Recorrente", "For a general meaning, use no article before the meal.",
    "Você disse", "...It's enough itself.", "Correção", "It's enough on its own.", "Quantifiers",
    "Here enough needs a complement such as on its own.",
    "Você disse", "...The family dinner, we always argue.", "Correção", "At family dinner, we always argue.",
    "Key vocabulary", "taboo", "B2 • Noun", "nonprofit", "B2 • Adjective",
]


def test_cambly_header_and_feedback():
    h = parse.cambly_header(CAMBLY_LINES)
    assert h == {"tutor": "Alex", "talk_pct": 65, "wpm": 131, "unique_words": 402, "duration_min": 30}
    fb = parse.cambly_feedback(CAMBLY_LINES)
    assert fb[0]["tag"] == "strength" and fb[0]["text"] == "You used connectors well."
    assert fb[1] == {"tag": "grammar", "original": "I have less things to do", "correction": "I have fewer things to do",
                     "explanation": "'Things' is countable."}
    assert fb[2]["tag"] == "vocabulary"
    assert not parse.cambly_pending(CAMBLY_LINES)
    assert parse.cambly_pending(["Preparando sua avaliação. Você pode sair"])


def test_preply_parsing():
    assert parse.preply_header(PREPLY_LINES) == {"learner_min": 27, "talk_pct": 57, "topic": "Handling tough questions"}
    fb = parse.preply_feedback(PREPLY_LINES)
    assert len(fb) == 2  # the repeated item is dropped
    assert fb[0]["original"] == "The family dinner, we always argue."
    assert fb[0]["tag"] == "Articles" and fb[0]["explanation"].startswith("For a general meaning")
    assert fb[1]["explanation"].startswith("Here enough")
    assert parse.preply_vocabulary(PREPLY_LINES) == ["taboo (B2, Noun)", "nonprofit (B2, Adjective)"]


def test_rawfile_roundtrip(tmp_path):
    meta = {"source": "cambly", "id": "abc", "date": "2026-09-08", "time": "08:30", "tutor": "Alex", "talk_pct": 65}
    fb = parse.cambly_feedback(CAMBLY_LINES)
    text = rawfile.render(meta, fb, ["taboo (B2, Noun)"], [("T", "Hi!"), ("L", 'I said "hello"')])
    p = tmp_path / "cambly_lesson_2026-09-08.md"
    p.write_text(text, encoding="utf-8")
    back = rawfile.parse(p)
    assert back["meta"]["talk_pct"] == 65 and back["meta"]["tutor"] == "Alex"
    assert back["feedback"][1]["orig"] == "I have less things to do"
    assert back["feedback"][1]["expl"] == "'Things' is countable."
    assert back["feedback"][0]["tag"] == "strength" and back["feedback"][0]["text"] == "You used connectors well."
    assert back["transcript"] == [("T", "Hi!"), ("L", "I said 'hello'")]
    assert rawfile.filename("cambly", "2026-09-08", {"cambly_lesson_2026-09-08.md"}) == "cambly_lesson_2026-09-08_2.md"


@pytest.mark.parametrize("orig,corr,cat", [
    ("I have less things", "I have fewer things", "comparatives-adverbs"),
    ("at the evening", "in the evening", "prepositions"),
    ("in a easy way", "in an easy way", "articles"),
    ("this thing don't work", "this thing doesn't work", "subject-verb-agreement"),
    ("I think I can live there", "I think I can't live there", "polarity"),
    ("my job is talk to people", "my job is talking to people", "verb-forms"),
    ("He is a florist engineer", "He is a forest engineer", "vocabulary"),
])
def test_classify(orig, corr, cat):
    assert review.classify(orig, corr) == cat


def test_schema_validation():
    good = {"errors": [{"category": "articles", "original": "a", "correction": "b", "explanation": "c",
                        "confidence": "high"}], "strengths": ["x"], "vocabulary": []}
    assert schema.validate(good)["errors"][0]["category"] == "articles"
    with pytest.raises(ValueError, match="category"):
        schema.validate({**good, "errors": [{**good["errors"][0], "category": "spelling"}]})


def test_offline_review_to_notebook(tmp_path, monkeypatch):
    for name in ("RAW", "ANALYSIS", "REVIEWS", "ERRORS", "OUTPUT"):
        monkeypatch.setattr(config, name, tmp_path / getattr(config, name).relative_to(config.ROOT))
    config.RAW.mkdir(parents=True)
    src = config.REPO / "examples" / "raw" / "cambly_lesson_2026-01-05.md"
    (config.RAW / src.name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    cfg = config._merge(config.DEFAULTS, {})
    review.run_offline(cfg)
    data = aggregate.run()
    assert len(data["errors"]) >= 3 and data["stats"][0]["talk"] == 58
    assert insights.plan(data)[0]["tasks"]
    html = build.render(data, cfg)
    assert build.MARKER not in html and '"errors"' in html


def test_example_builds():
    data = json.loads((config.REPO / "examples" / "errors.json").read_text(encoding="utf-8"))
    html = build.render(data, config._merge(config.DEFAULTS, {}))
    assert html.startswith("<!doctype html>") and "</script>" in html


class _FakeMessages:
    def __init__(self, payload):
        self.payload, self.kwargs = payload, None

    def create(self, **kwargs):
        self.kwargs = kwargs
        block = type("Block", (), {"type": "text", "text": json.dumps(self.payload)})()
        return type("Resp", (), {"stop_reason": "end_turn", "content": [block], "model": kwargs["model"]})()


def test_api_review_request(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "REVIEWS", tmp_path / "reviews")
    payload = {"errors": [{"category": "prepositions", "original": "wake up 6 and 30", "correction": "wake up at 6:30",
                           "explanation": "Use at with clock times.", "confidence": "high"}],
               "strengths": ["Clear routine."], "vocabulary": []}
    fake = _FakeMessages(payload)
    client = type("Client", (), {"beta": type("Beta", (), {"messages": fake})()})()
    cfg = config._merge(config.DEFAULTS, {"learner": {"explanation_language": "pt-BR"}})
    out = review.review_api(config.REPO / "examples" / "raw" / "cambly_lesson_2026-01-05.md", cfg, client)
    k = fake.kwargs
    assert k["model"] == "claude-sonnet-5-5" and k["fallbacks"] == "default"
    assert k["output_config"]["format"]["schema"] is schema.REVIEW_SCHEMA
    assert k["system"][0]["cache_control"] == {"type": "ephemeral"} and "pt-BR" in k["system"][0]["text"]
    assert "6 and 30" in k["messages"][0]["content"]
    assert out["method"] == "api" and out["errors"][0]["category"] == "prepositions"


def test_import_copied_pages(tmp_path, monkeypatch):
    from lessonreview import importer
    monkeypatch.setattr(config, "RAW", tmp_path / "raw")
    config.RAW.mkdir()
    cfg = config._merge(config.DEFAULTS, {"period": {"from": "2026-01-01", "to": "2026-03-31"}})
    manifest = {"lessons": []}
    inbox = config.REPO / "examples" / "inbox"

    name, msg = importer.import_file(inbox / "cambly_copied_page.txt", cfg, manifest)
    lesson = rawfile.parse(config.RAW / name)
    assert name == "cambly_lesson_2026-01-12.md"
    assert lesson["meta"]["tutor"] == "Alex" and lesson["meta"]["talk_pct"] == 61 and lesson["meta"]["wpm"] == 128
    assert [f["orig"] for f in lesson["feedback"] if f["orig"]] == [
        "I went there in my car with three friend.", "We had a lot of fun in the parade, it was very funny."]
    assert lesson["transcript"][0] == ("?", "Hi! How was your weekend?") and len(lesson["transcript"]) == 6

    name, msg = importer.import_file(inbox / "preply_copied_page.txt", cfg, manifest)
    lesson = rawfile.parse(config.RAW / name)
    assert name == "preply_lesson_2026-01-14.md"  # year comes from the configured period
    assert lesson["meta"]["tutor"] == "Sam" and lesson["meta"]["learner_min"] == 26
    assert lesson["feedback"][0]["orig"] == "I didn't knew the answer in that moment."
    assert lesson["vocabulary"] == ["push back (B2, expression)", "off the top of my head (B2, expression)"]

    assert importer.import_file(inbox / "preply_copied_page.txt", cfg, manifest)[1] == "already imported"
    assert len(manifest["lessons"]) == 2


@pytest.mark.parametrize("line,expected", [
    ("8 de setembro de 2026", "2026-09-08"),
    ("September 8, 2026", "2026-09-08"),
    ("24 de ago., 18:30 – 19:20", "2026-08-24"),
    ("Tuesday, Aug 24 · 18:30", "2026-08-24"),
])
def test_find_date(line, expected):
    from lessonreview import importer
    cfg = config._merge(config.DEFAULTS, {"period": {"from": "2026-08-01", "to": "2026-10-31"}})
    assert importer.find_date(["Header", line], cfg) == expected


def test_ui_paste_import_and_server(tmp_path, monkeypatch):
    import threading
    import urllib.error
    import urllib.request
    from http.server import HTTPServer

    from lessonreview import importer, ui
    for name in ("RAW", "ANALYSIS", "REVIEWS", "ERRORS", "OUTPUT", "MANIFEST"):
        monkeypatch.setattr(config, name, tmp_path / getattr(config, name).relative_to(config.ROOT))
    monkeypatch.setattr(importer, "INBOX", tmp_path / "inbox")
    cfg = config._merge(config.DEFAULTS, {"period": {"from": "2026-01-01", "to": "2026-03-31"}})
    page = (config.REPO / "examples" / "inbox" / "cambly_copied_page.txt").read_text(encoding="utf-8")

    assert ui.paste_import(page, cfg)["ok"]
    assert ui.paste_import(page, cfg) == {"ok": False, "message": "Skipped: already imported."}
    assert not ui.paste_import("hello", cfg)["ok"]
    assert len(list(importer.INBOX.glob("*.txt"))) == 1  # failed pastes leave nothing behind
    s = ui.state(cfg)
    assert [l["file"] for l in s["lessons"]] == ["cambly_lesson_2026-01-12.md"] and s["pending"] == 1

    ui.Handler.cfg = cfg
    server = HTTPServer(("127.0.0.1", 0), ui.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        def call(path, body=None, ctype="application/json"):
            req = urllib.request.Request(base + path, data=body, headers={"Content-Type": ctype} if body else {})
            try:
                with urllib.request.urlopen(req) as r:
                    return r.status, json.loads(r.read())
            except urllib.error.HTTPError as e:
                return e.code, None

        with urllib.request.urlopen(base + "/") as r:
            assert '"live": true' in r.read().decode("utf-8")  # the notebook, with the Lessons screen
        assert call("/api/state")[1]["pending"] == 1
        assert call("/api/run/review-offline", b"{}")[1]["ok"]
        assert call("/api/state")[1]["lessons"][0]["reviewed"]
        assert call("/api/run/review-offline", b"{}", "text/plain")[0] == 403  # cross-site form posts are refused
        assert call("/api/run/extract", b"{}")[0] == 404
        # automated extraction never starts unless the user ticked the risk box on the page
        assert not call("/api/extract", b"{}")[1]["ok"]
        assert not call("/api/extract", b'{"accept_terms_risk": "yes"}')[1]["ok"]
        assert not ui.JOB["running"]
        assert call("/api/state")[1]["history"]["cambly"].startswith("https://www.cambly.com/")
        assert call("/output/../config.json")[0] == 404
    finally:
        server.shutdown()


def test_ui_api_key_and_mcp(tmp_path, monkeypatch):
    from lessonreview import ui
    monkeypatch.setattr(config, "SECRETS", tmp_path / "secrets.json")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert ui.api_status()["anthropic"] == {"source": None} and config.api_key() is None
    assert not ui.save_api_key("not-a-key")["ok"] and not config.SECRETS.exists()
    config.write_json(config.SECRETS, {"anthropic_api_key": "sk-ant-secret-1234"})
    assert ui.api_status()["anthropic"] == {"source": "saved", "hint": "…1234"}  # the page never gets the key itself
    assert "secret" not in json.dumps(ui.api_status())
    assert ui.save_api_key("")["ok"] and not config.SECRETS.exists()

    desktop = tmp_path / "Claude" / "claude_desktop_config.json"
    monkeypatch.setattr(ui, "desktop_config_path", lambda: desktop)
    assert not ui.connect_desktop()["ok"]  # Claude Desktop not installed
    desktop.parent.mkdir()
    desktop.write_text('{"mcpServers": {"other": {"command": "x"}}, "theme": "dark"}', encoding="utf-8")
    assert ui.connect_desktop()["ok"]
    data = json.loads(desktop.read_text(encoding="utf-8"))
    assert data["theme"] == "dark" and set(data["mcpServers"]) == {"other", "english-lesson-review"}
    assert data["mcpServers"]["english-lesson-review"]["args"] == ["-m", "lessonreview.mcp_server"]
    assert desktop.with_suffix(".json.bak").exists() and ui.mcp_status()["desktop_connected"]


def test_other_provider_review(tmp_path, monkeypatch):
    from lessonreview import providers, ui
    monkeypatch.setattr(config, "SECRETS", tmp_path / "secrets.json")
    monkeypatch.setattr(providers, "check", lambda s: None)
    assert not ui.save_provider({"preset": "openai", "model": "m"})["ok"]  # OpenAI needs a key
    assert not ui.save_provider({"preset": "custom", "base_url": "ftp://x", "model": "m"})["ok"]
    assert ui.save_provider({"preset": "ollama", "model": "qwen3:14b"})["ok"]  # local: no key
    assert providers.settings()["base_url"] == "http://localhost:11434/v1"
    assert ui.save_provider({"preset": "openai", "model": "m", "key": "sk-proj-abcd9876"})["ok"]
    assert ui.save_provider({"preset": "openai", "model": "m2"})["ok"]  # blank key keeps the saved one
    assert providers.settings() == {"preset": "openai", "base_url": "https://api.openai.com/v1", "model": "m2",
                                    "api_key": "sk-proj-abcd9876"}
    status = ui.api_status()
    assert status["provider"] == "openai" and status["openai"]["hint"] == "…9876" and "abcd" not in json.dumps(status)
    config.write_json(config.SECRETS, {**config.read_json(config.SECRETS), "anthropic_api_key": "sk-ant-x"})
    assert ui.save_provider({"use": "anthropic"})["ok"] and providers.settings() is None
    assert config.read_json(config.SECRETS)["openai"]["model"] == "m2"  # kept for switching back
    assert ui.save_provider({"use": "openai"})["ok"] and providers.settings()["model"] == "m2"
    assert ui.save_provider({"remove": True})["ok"] and "openai" not in config.read_json(config.SECRETS)
    assert not ui.save_provider({"use": "openai"})["ok"]  # nothing saved to switch to

    payload = {"errors": [{"category": "prepositions", "original": "wake up 6 and 30", "correction": "wake up at 6:30",
                           "explanation": "Use at with clock times.", "confidence": "high"}],
               "strengths": [], "vocabulary": []}
    calls = []

    def fake(s, path, body):  # rejects json_schema the first time, like servers that only have JSON mode
        calls.append(json.loads(json.dumps(body)))
        if len(calls) == 1:
            raise providers.ProviderError("HTTP 400: response_format", 400)
        return {"model": "m2", "choices": [{"finish_reason": "stop",
                                            "message": {"content": "```json\n" + json.dumps(payload) + "\n```"}}]}

    cfg = config._merge(config.DEFAULTS, {})
    s = {"base_url": "https://x/v1", "model": "m2", "api_key": "k"}
    data, model = providers.review(config.REPO / "examples" / "raw" / "cambly_lesson_2026-01-05.md", cfg, s, fake)
    assert data == payload and model == "m2"
    assert calls[0]["response_format"]["json_schema"]["schema"] is not None and calls[0]["model"] == "m2"
    assert calls[1]["response_format"] == {"type": "json_object"} and "JSON schema" in calls[1]["messages"][0]["content"]
    assert "6 and 30" in calls[0]["messages"][1]["content"]
