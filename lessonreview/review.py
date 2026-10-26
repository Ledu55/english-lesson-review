"""Step 2: turn each raw lesson into a review (analysis/reviews/<lesson>.json).

Three ways to produce a review, all writing the same format:
- api:     one Claude API call per lesson with a JSON schema (needs ANTHROPIC_API_KEY or `ant auth login`)
- mcp:     an MCP host (Claude Desktop / Claude Code) reads the lesson and calls save_review (see mcp_server.py)
- offline: no LLM; uses the corrections the platform already gave, sorted into categories by rules
"""
import json
import re
import sys
import time

from . import config, rawfile
from .categories import CATEGORIES
from .schema import REVIEW_SCHEMA, validate

INSTRUCTIONS = """You are an experienced ESL teacher reviewing one lesson transcript of an English learner.
Learner: native {native_language} speaker, level {level}{background}.

Find the learner's real errors: grammar, prepositions, verb forms, tenses, agreement, articles,
comparatives, inverted polarity (said "can" but meant "can't"), word choice and false friends,
and mis-transcribed words that reveal a pronunciation problem.

Rules:
- Only the learner's lines count ("L:" in the transcript). Tutor lines ("T:") are context.
- Lines marked "?:" come from copied page text with no speaker names, and one turn may be split over several
  lines. Count a line as the learner's only when that is clear (the tutor asks questions, corrects and models
  language; the learner answers and makes non-native errors). When unsure, use confidence "low".
- Ignore normal spoken disfluency: fillers, restarts, "like", unfinished phrases.
- Do not invent errors. When you can't tell a real error from a transcription artifact, set confidence "low".
- "original" is the learner's words verbatim (the shortest span that shows the error). "correction" is the natural fix.
- Platform feedback lines are corrections the platform already suggested. Keep the ones that are right,
  drop the ones that are wrong, and add what they missed.
- If the same mistake repeats in the lesson, report it once and say it repeats in the explanation.
- "explanation": one or two short sentences written in {explanation_language}.
- "strengths": up to 3 specific things the learner did well in this lesson.
- "vocabulary": false friends and wrong words worth memorizing (wrong word -> right word, short note).

Categories: {categories}
"""


def instructions(cfg):
    learner = cfg["learner"]
    cats = "; ".join(f"{k} ({v['name']}: {v['hint']})" for k, v in CATEGORIES.items())
    return INSTRUCTIONS.format(
        native_language=learner["native_language"], level=learner["level"],
        background=f", {learner['background']}" if learner.get("background") else "",
        explanation_language=learner["explanation_language"], categories=cats)


def pending():
    """Raw files that have no review yet, oldest first."""
    done = {p.stem for p in config.REVIEWS.glob("*.json")}
    files = sorted(config.RAW.glob("*.md"), key=lambda p: (rawfile.parse(p)["meta"].get("date", ""), p.name))
    return [p for p in files if p.stem not in done]


def lesson_text(path):
    return path.read_text(encoding="utf-8")


def save(path, review, method, model=None):
    lesson = rawfile.parse(path)
    out = {
        "file": path.name,
        "source": lesson["meta"].get("source"),
        "lesson": lesson["meta"].get("date"),
        "method": method,
        "model": model,
        "reviewed_at": time.strftime("%Y-%m-%d %H:%M"),
        **validate(review),
    }
    config.write_json(config.REVIEWS / f"{path.stem}.json", out)
    return out


# --- API reviewer -------------------------------------------------------------

def review_api(path, cfg, client=None):
    import anthropic

    client = client or anthropic.Anthropic()
    model = cfg["review"]["model"]
    response = client.beta.messages.create(
        model=model,
        max_tokens=cfg["review"]["max_tokens"],
        # On a safety decline the API retries the request on a fallback model it picks.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=[{"type": "text", "text": instructions(cfg), "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": f"Review this lesson.\n\n<lesson>\n{lesson_text(path)}\n</lesson>"}],
        output_config={"format": {"type": "json_schema", "schema": REVIEW_SCHEMA}},
    )
    if response.stop_reason == "refusal":
        raise RuntimeError(f"the model declined to review {path.name}")
    if response.stop_reason == "max_tokens":
        raise RuntimeError(f"{path.name}: response hit max_tokens; raise review.max_tokens in config.json")
    text = next(b.text for b in response.content if b.type == "text")
    return save(path, json.loads(text), "api", response.model)


def run_api(cfg, limit=None):
    import anthropic

    client = anthropic.Anthropic()
    todo = pending()[:limit] if limit else pending()
    if not todo:
        print("Nothing to review: every raw lesson already has a review.")
    for path in todo:
        try:
            r = review_api(path, cfg, client)
            print(f"reviewed {path.name}: {len(r['errors'])} errors")
        except anthropic.AuthenticationError:
            sys.exit("No valid API credentials. Set ANTHROPIC_API_KEY (or run `ant auth login`), "
                     "use the MCP server, or run `review --offline`.")
        except anthropic.RateLimitError:
            sys.exit("Rate limited. Run the command again later; finished lessons are kept.")
        except (anthropic.APIStatusError, anthropic.APIConnectionError, RuntimeError) as e:
            print(f"skipped {path.name}: {e}")


# --- Offline reviewer -----------------------------------------------------------

PREPOSITIONS = {"in", "on", "at", "to", "for", "of", "by", "with", "about", "from", "into", "onto", "over",
                "under", "through", "during", "since", "until", "within", "without", "between", "among", "per"}
ARTICLES = {"a", "an", "the"}
AGREEMENT = [{"do", "does"}, {"don't", "doesn't"}, {"was", "were"}, {"has", "have"}, {"is", "are"},
             {"wasn't", "weren't"}, {"isn't", "aren't"}, {"this", "these"}, {"that", "those"}]
COMPARE = {"less", "fewer", "more", "most", "much", "many", "very", "too"}
WORD = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")


def _tokens(s):
    return [w.lower() for w in WORD.findall(s.replace("’", "'"))]


def classify(original, correction, platform_tag=""):
    """Best-effort category for a correction, from the words that changed."""
    o, c = _tokens(original), _tokens(correction)
    removed, added = set(o) - set(c), set(c) - set(o)
    changed = removed | added
    tag = platform_tag.lower()
    if not changed:
        return "other"
    if {"can", "can't", "cannot"} & removed and {"can", "can't", "cannot"} & added or \
            {"will", "won't"} & removed and {"will", "won't"} & added:
        return "polarity"
    if changed <= ARTICLES:
        return "articles"
    if changed <= PREPOSITIONS | ARTICLES and changed & PREPOSITIONS:
        return "prepositions"
    if any(pair <= changed for pair in AGREEMENT) or \
            any(a == r + "s" or a == r + "es" or r == a + "s" for a in added for r in removed):
        return "subject-verb-agreement"
    if changed & COMPARE or any(w.endswith("er") or w.endswith("ly") for w in added):
        return "comparatives-adverbs"
    if any(w.endswith("ing") for w in added) or {"am", "is", "are", "do", "did", "to", "'m"} & added:
        return "verb-forms"
    if {"will", "would", "have", "had", "been"} & changed or \
            any(a == r + "ed" or a == r + "d" for a in added for r in removed):
        return "tenses"
    if "vocab" in tag or "vocabul" in tag or "word" in tag or len(changed) <= 2:
        return "vocabulary"
    return "other"


def review_offline(path, cfg):
    lesson = rawfile.parse(path)
    errors, strengths, vocab = [], [], []
    for f in lesson["feedback"]:
        tag = f.get("tag", "")
        if f.get("orig"):
            cat = classify(f["orig"], f["corr"], tag)
            errors.append({"category": cat, "original": f["orig"], "correction": f["corr"],
                           "explanation": f.get("expl") or CATEGORIES[cat]["hint"], "confidence": "medium"})
            if cat == "vocabulary" and len(_tokens(f["orig"])) <= 4:
                vocab.append({"wrong": f["orig"], "right": f["corr"], "note": f.get("expl", "")})
        elif tag.lower().startswith("strength") and f.get("text"):
            strengths.append(f["text"])
    return save(path, {"errors": errors, "strengths": strengths[:3], "vocabulary": vocab}, "offline")


def run_offline(cfg, limit=None):
    todo = pending()[:limit] if limit else pending()
    if not todo:
        print("Nothing to review: every raw lesson already has a review.")
    for path in todo:
        r = review_offline(path, cfg)
        print(f"reviewed {path.name} offline: {len(r['errors'])} corrections from platform feedback")


def main(args, cfg):
    if args.offline:
        run_offline(cfg, args.limit)
    else:
        run_api(cfg, args.limit)
    from . import aggregate
    aggregate.run()
