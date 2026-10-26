# English Lesson Review

Pipeline: `extract` (Playwright, Cambly/Preply → `raw/*.md`) → `review` (→ `analysis/reviews/*.json`, merged into `analysis/errors.json`) → `build` (→ `output/notebook.html`, `output/voice_coach.md`). Commands: `python -m lessonreview <extract|review|build|all|status>`.

## When the user asks to review lessons
Use the `english-lesson-review` MCP tools (registered in `.mcp.json`): `next_lesson_to_review`, then `save_review` with a JSON string that follows the returned schema and instructions, until it reports no lessons left; then `build_notebook`. Review one lesson per call; do not read `raw/` files directly for this.

## Rules
- `raw/`, `analysis/`, `output/`, `manifest.json`, `config.json` and `.browser-profile/` hold the user's personal data. Never commit them, never copy their content into `examples/` or tests.
- Error categories live only in `lessonreview/categories.py`; the notebook, plan and voice coach read them from there.
- `notebook/template.html` is filled by `build.py` at the `/*__DATA__*/null` marker; keep the marker.
- Page-side extraction code is in `lessonreview/extract/js/`; parsing of page text is in `extract/parse.py` and must stay covered by `tests/`.
- Run `python -m pytest` after changes.
