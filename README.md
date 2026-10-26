# English Lesson Review

Turn your Cambly and Preply lessons into a personal practice notebook built from your own mistakes.

```
Cambly / Preply ──extract──▶ raw/*.md ──review──▶ analysis/errors.json ──build──▶ output/notebook.html
  (your browser)              one file             your errors, sorted            flashcards, fill the gap,
                              per lesson           into 9 types                   daily review, weekly plan
```

The notebook is one HTML file that works offline. It has:

- **Daily review**: spaced repetition over your real sentences. New and missed cards show as flashcards; cards you already know come back as fill-the-gap. Correct answers come back after 1, 2, 4, 8 and 16 days.
- **Flashcards** and **Fill the gap**, filterable by error type, with an optional read-aloud voice.
- **Diagnosis**: your recurring error types, how they changed over the period, and your strengths.
- **Weekly plan**: four weeks, one per most frequent error type.
- **Voice coach** (`output/voice_coach.md`): a system prompt for any voice assistant that drills your own errors.

Want to see it first? `python -m lessonreview build --example` builds the notebook from an anonymized sample of one learner's real errors.

## Requirements

- Python 3.10+
- Google Chrome (the extractor drives a real Chrome window)
- For the review step, one of:
  - an Anthropic API key, or
  - Claude Desktop or Claude Code (uses your Claude subscription through MCP), or
  - nothing at all, with `--offline` (lower quality, see below)

## Setup

```bash
git clone https://github.com/<you>/english-lesson-review.git
cd english-lesson-review
pip install -r requirements.txt
cp config.example.json config.json   # then edit it
```

`config.json`:

| Key | What it does |
|---|---|
| `period.from`, `period.to` | Which lessons to collect (`YYYY-MM-DD`). |
| `platforms` | `["cambly", "preply"]`, or just one. |
| `learner.native_language` | Used in the review prompt (helps spot false friends). |
| `learner.explanation_language` | Language of the explanations, e.g. `en`, `pt-BR`, `es`. |
| `learner.level`, `learner.background` | Context for the reviewer. |
| `review.model` | Model for API reviews. Default `claude-sonnet-5-5`. |
| `browser.channel` | `chrome` uses your installed Chrome. Set to `null` to use Playwright's Chromium (run `playwright install chromium` first). |
| `browser.cdp_url` | Optional: attach to a Chrome you started with `--remote-debugging-port=9222`, e.g. `http://localhost:9222`. |

## Step 1: extract your lessons

```bash
python -m lessonreview extract              # both platforms
python -m lessonreview extract --platform cambly --limit 5
```

A Chrome window opens with its own profile (`.browser-profile/`, never committed). The first time, log in to Cambly and Preply in that window and press Enter in the terminal. Your session is kept for later runs.

Each lesson becomes one file in `raw/`, and `manifest.json` records progress. If something fails halfway (a lesson whose feedback is still being prepared, a network error), run the command again: finished lessons are skipped.

What gets saved:

| | Cambly | Preply |
|---|---|---|
| Full transcript, split by speaker | Yes | No (Preply doesn't provide one) |
| Platform corrections ("You said / Suggestion") | Yes | Yes |
| Talk time, words per minute, unique words | Yes | Talk time only |
| Key vocabulary | No | Yes |

You can also write raw files by hand, for lessons from any other platform. The format is in [`lessonreview/rawfile.py`](lessonreview/rawfile.py), with an example in [`examples/raw/`](examples/raw/).

## Step 2: review

Pick one of three ways. They all write the same files to `analysis/`, and you can mix them.

**A. Claude API** (best quality, fully automatic)

```bash
export ANTHROPIC_API_KEY=sk-ant-...     # PowerShell: $env:ANTHROPIC_API_KEY="sk-ant-..."
python -m lessonreview review
```

One request per lesson, with the answer constrained to a JSON schema. Only lessons without a review are sent, so re-running is cheap. A 30-minute lesson is roughly 10k input tokens.

**B. Claude Desktop or Claude Code over MCP** (no API key; uses your subscription)

In Claude Code, open this folder: `.mcp.json` registers the server. Then ask:

> Review all pending lessons with the english-lesson-review tools, then build the notebook.

For Claude Desktop, add this to `claude_desktop_config.json` and restart it:

```json
{
  "mcpServers": {
    "english-lesson-review": {
      "command": "python",
      "args": ["-m", "lessonreview.mcp_server"],
      "env": { "LESSONREVIEW_HOME": "C:/path/to/english-lesson-review", "PYTHONPATH": "C:/path/to/english-lesson-review" }
    }
  }
}
```

The server exposes `status`, `next_lesson_to_review`, `save_review` and `build_notebook`. Claude reads one lesson, finds the errors, and saves them. The server validates every review against the same schema the API path uses.

**C. Offline** (no LLM)

```bash
python -m lessonreview review --offline
```

Uses only the corrections Cambly and Preply already gave you, and sorts them into error types with simple rules. It misses what the platforms miss, like inverted meaning ("can" for "can't") or false friends, and it adds no strengths.

## Step 3: build the notebook

```bash
python -m lessonreview build
```

Open `output/notebook.html` in your browser. Progress (card boxes, streak, plan checkboxes) is saved in that browser's local storage.

`python -m lessonreview all` runs the three steps in a row, and `python -m lessonreview status` shows where you are.

## Error types

Every reviewer uses the same nine types, defined in [`lessonreview/categories.py`](lessonreview/categories.py) with the rule, drills and plan tasks for each: prepositions, vocabulary and false friends, verb forms, tenses, subject-verb agreement, comparatives and adverbs, articles, can/can't (polarity), and other.

## Privacy

- Your lessons, reviews and notebook stay on your machine. `raw/`, `analysis/`, `output/`, `manifest.json`, `config.json` and `.browser-profile/` are all in `.gitignore`.
- With the API or MCP review, lesson transcripts are sent to Anthropic to be reviewed. The offline review sends nothing anywhere.
- The `examples/` data comes from one learner, with tutor names, companies and places removed.

## Disclaimer

This project is not affiliated with Cambly or Preply. The extractor reads pages from your own logged-in account, for your personal study. It depends on how those sites are built today and will break when they change. Check each platform's terms before using it.

If the extractor breaks, the page-side code is in [`lessonreview/extract/js/`](lessonreview/extract/js/) and the text parsing in [`lessonreview/extract/parse.py`](lessonreview/extract/parse.py), with tests in [`tests/`](tests/).

## Development

```bash
pip install -r requirements.txt pytest
python -m pytest
```

## License

Public domain ([Unlicense](LICENSE)). Use it however you like.
