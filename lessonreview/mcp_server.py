"""MCP server: lets Claude Desktop or Claude Code do the review with your subscription, no API key.

The host model reads one lesson at a time and sends back a review; this server validates it against the
same schema the API reviewer uses and saves it. Extraction stays a terminal command (it needs a browser).

Run: python -m lessonreview.mcp_server   (stdio transport)
"""
import contextlib
import functools
import json
import sys

from mcp.server.mcpserver import MCPServer

from . import aggregate, build, config, review
from .schema import REVIEW_SCHEMA

server = MCPServer(
    "english-lesson-review",
    instructions=(
        "Reviews English lessons saved by the lessonreview extractor. Workflow: call next_lesson_to_review, "
        "follow its instructions to find the learner's errors, call save_review with the result, repeat until "
        "no lessons are left, then call build_notebook."
    ),
)


def quiet(fn):
    """stdout carries the MCP protocol, so progress messages printed by the pipeline go to stderr."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with contextlib.redirect_stdout(sys.stderr):
            return fn(*args, **kwargs)
    return wrapper


@server.tool()
@quiet
def status() -> dict:
    """How many lessons are extracted, reviewed and waiting for review."""
    raw = sorted(p.name for p in config.RAW.glob("*.md"))
    waiting = [p.name for p in review.pending()]
    return {"project": str(config.ROOT), "raw_lessons": len(raw), "waiting_for_review": waiting,
            "notebook_built": (config.OUTPUT / "notebook.html").exists()}


@server.tool()
@quiet
def next_lesson_to_review() -> dict:
    """The oldest lesson without a review: its text, the review instructions and the JSON schema to follow."""
    todo = review.pending()
    if not todo:
        return {"done": True, "message": "Every lesson is reviewed. Call build_notebook."}
    path = todo[0]
    return {"done": False, "file": path.name, "remaining_after_this": len(todo) - 1,
            "instructions": review.instructions(config.load()), "schema": REVIEW_SCHEMA,
            "lesson": review.lesson_text(path)}


@server.tool()
@quiet
def save_review(file: str, review_json: str) -> str:
    """Save the review of one lesson. review_json is a JSON object with errors, strengths and vocabulary,
    following the schema from next_lesson_to_review."""
    path = config.RAW / file
    if path.parent != config.RAW or not path.exists():
        return f"Error: {file} is not a lesson in raw/."
    try:
        saved = review.save(path, json.loads(review_json), "mcp")
    except (json.JSONDecodeError, ValueError) as e:
        return f"Error, review not saved. Fix and call save_review again: {e}"
    return f"Saved {len(saved['errors'])} errors for {file}. {len(review.pending())} lessons left."


@server.tool()
@quiet
def build_notebook() -> str:
    """Merge all reviews into analysis/errors.json and build output/notebook.html and output/voice_coach.md."""
    data = aggregate.run()
    if not data["errors"]:
        return "No errors yet: review some lessons first."
    cfg = config.load()
    config.OUTPUT.mkdir(exist_ok=True)
    (config.OUTPUT / "notebook.html").write_text(build.render(data, cfg), encoding="utf-8")
    from . import coach
    (config.OUTPUT / "voice_coach.md").write_text(coach.render(data, cfg), encoding="utf-8")
    return f"Built {config.OUTPUT / 'notebook.html'} with {len(data['errors'])} errors. Open it in a browser."


if __name__ == "__main__":
    server.run()
