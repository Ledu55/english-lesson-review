"""Reviews through providers other than Anthropic, over the OpenAI-compatible chat completions API.

OpenAI, Google Gemini, OpenRouter, Groq, Mistral, DeepSeek, and local servers (Ollama, LM Studio) all accept
the same request, so one client covers them. The prompt and schema are the ones the Anthropic reviewer uses.
Settings come from secrets.json (saved on the `ui` page): {"provider": "openai", "openai": {base_url, model, api_key}}.
"""
import json
import urllib.error
import urllib.request

from . import config

# name, base URL, example model, whether it needs a key, where to get one
PRESETS = {
    "openai": ("OpenAI", "https://api.openai.com/v1", "gpt-5-mini", True, "https://platform.openai.com/api-keys"),
    "gemini": ("Google Gemini", "https://generativelanguage.googleapis.com/v1beta/openai", "gemini-2.5-flash", True,
               "https://aistudio.google.com/apikey"),
    "openrouter": ("OpenRouter", "https://openrouter.ai/api/v1", "openai/gpt-5-mini", True, "https://openrouter.ai/keys"),
    "groq": ("Groq", "https://api.groq.com/openai/v1", "openai/gpt-oss-120b", True, "https://console.groq.com/keys"),
    "mistral": ("Mistral", "https://api.mistral.ai/v1", "mistral-medium-latest", True, "https://console.mistral.ai/api-keys"),
    "deepseek": ("DeepSeek", "https://api.deepseek.com/v1", "deepseek-chat", True, "https://platform.deepseek.com/api_keys"),
    "ollama": ("Ollama (local)", "http://localhost:11434/v1", "qwen3:14b", False, None),
    "lmstudio": ("LM Studio (local)", "http://localhost:1234/v1", "", False, None),
    "custom": ("Other (OpenAI-compatible)", "", "", False, None),
}


class ProviderError(RuntimeError):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


def settings():
    """The saved provider settings, or None when reviews go to Anthropic."""
    data = config.read_json(config.SECRETS, {}) or {}
    return data.get("openai") if data.get("provider") == "openai" else None


def _request(s, path, body=None, timeout=600):
    headers = {"Content-Type": "application/json"}
    if s.get("api_key"):
        headers["Authorization"] = f"Bearer {s['api_key']}"
    req = urllib.request.Request(s["base_url"].rstrip("/") + path, headers=headers,
                                 data=json.dumps(body).encode("utf-8") if body is not None else None)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise ProviderError(f"HTTP {e.code}: {detail}", e.code) from None
    except urllib.error.URLError as e:
        raise ProviderError(f"can't reach {s['base_url']}: {e.reason}") from None


def check(s):
    """Raise ProviderError unless the server answers and accepts the key (listing models is free)."""
    _request(s, "/models", timeout=20)


def review(path, cfg, s, request=_request):
    """Review one lesson; returns the review dict, not yet validated or saved."""
    from .review import instructions, lesson_text
    from .schema import REVIEW_SCHEMA
    messages = [{"role": "system", "content": instructions(cfg)},
                {"role": "user", "content": f"Review this lesson.\n\n<lesson>\n{lesson_text(path)}\n</lesson>"}]
    body = {"model": s["model"], "messages": messages, "max_tokens": cfg["review"]["max_tokens"],
            "response_format": {"type": "json_schema", "json_schema": {"name": "review", "schema": REVIEW_SCHEMA}}}
    try:
        out = request(s, "/chat/completions", body)
    except ProviderError as e:
        if e.status != 400:
            raise
        # Some servers only take plain JSON mode: put the schema in the prompt instead.
        messages[0]["content"] += f"\nReply with one JSON object that follows this JSON schema:\n{json.dumps(REVIEW_SCHEMA)}"
        body["response_format"] = {"type": "json_object"}
        out = request(s, "/chat/completions", body)
    choice = out["choices"][0]
    if choice.get("finish_reason") == "length":
        raise ProviderError(f"{path.name}: response hit max_tokens; raise review.max_tokens in config.json")
    text = (choice["message"].get("content") or "").strip()
    if text.startswith("```"):  # some models wrap JSON in a code fence despite JSON mode
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    try:
        return json.loads(text), out.get("model") or s["model"]
    except ValueError:
        raise ProviderError(f"{path.name}: the model didn't return valid JSON") from None
