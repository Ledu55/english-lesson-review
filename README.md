# English Lesson Review

Turn your Cambly and Preply lessons into a personal practice notebook built from your own mistakes.

```
Cambly / Preply ──import───▶ raw/*.md ──review──▶ analysis/errors.json ──build──▶ output/notebook.html
  (pages you copy)            one file             your errors, sorted            flashcards, fill the gap,
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
- For the review step, one of:
  - an Anthropic API key, or
  - Claude Desktop or Claude Code (uses your Claude subscription through MCP), or
  - nothing at all, with `--offline` (lower quality, see below)

## Setup

```bash
git clone https://github.com/Ledu55/english-lesson-review.git
cd english-lesson-review
pip install -r requirements.txt
cp config.example.json config.json   # then edit it
```

`config.json`:

| Key | What it does |
|---|---|
| `period.from`, `period.to` | Your study period (`YYYY-MM-DD`). Also used to fill in the year on Preply pages, which don't show it. |
| `platforms` | `["cambly", "preply"]`, or just one. |
| `learner.native_language` | Used in the review prompt (helps spot false friends). |
| `learner.explanation_language` | Language of the explanations, e.g. `en`, `pt-BR`, `es`. |
| `learner.level`, `learner.background` | Context for the reviewer. |
| `review.model` | Model for API reviews. Default `claude-sonnet-5-5`. |

## Step 1: copy your lessons

For each lesson, paste the page text into a `.txt` file in the `inbox/` folder (one file per lesson, any name):

- **Cambly**: open the lesson in *Progress → Lesson history*. On the **FEEDBACK** tab press Ctrl+A, Ctrl+C and paste into the file. Then open the **TRANSCRIPT** tab, Ctrl+A, Ctrl+C, and paste below in the same file.
- **Preply**: open the lesson's insights page, click **See all grammar feedback** and **See all vocabulary**, then Ctrl+A, Ctrl+C and paste.

Then:

```bash
python -m lessonreview import
```

The platform, date, tutor, talk time and corrections are read from the text. Files already imported are skipped, so you can keep adding lessons to `inbox/` and re-run. If a date or platform can't be detected, pass `--date 2026-09-08` or `--platform cambly` with the file name.

Each lesson becomes one file in `raw/`. What you get:

| | Cambly | Preply |
|---|---|---|
| Platform corrections ("You said / Suggestion") | Yes | Yes |
| Transcript | Yes, but without speaker names (copied text doesn't include them) | No (Preply doesn't provide one) |
| Talk time, words per minute, unique words | Yes | Talk time only |
| Key vocabulary | No | Yes |

[`examples/inbox/`](examples/inbox/) shows what pasted pages look like. You can also write raw files by hand, for lessons from any other platform: the format is in [`lessonreview/rawfile.py`](lessonreview/rawfile.py), with an example in [`examples/raw/`](examples/raw/).

### Automated extraction (not recommended)

There is also an extractor that drives Chrome and collects every lesson in the period by itself. **Both platforms' terms forbid this**, and using it can get your account suspended:

- Cambly User Agreement, section 7: no "robô, spider, scraper ou outro meio automatizado para acessar a Plataforma".
- Preply Terms of Service: "You agree not to view, copy, or procure content or information from the Preply Platform by automated means".

It is off by default. If you accept that risk for your own account:

```bash
pip install playwright
python -m lessonreview extract --accept-terms-risk --limit 3
```

A Chrome window opens with its own profile (`.browser-profile/`). Log in to each platform there the first time. It saves after every lesson and resumes from `manifest.json`. Extra settings: `browser.channel` (`chrome` or `null` for Playwright's Chromium) and `browser.cdp_url` (attach to a Chrome started with `--remote-debugging-port`).

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

`python -m lessonreview all` imports what's in `inbox/`, reviews and builds, and `python -m lessonreview status` shows where you are.

Prefer clicking to typing commands? `python -m lessonreview ui` opens the notebook at `http://localhost:8765` with an extra **Lessons** screen, where you paste lessons straight in (no `.txt` files needed), see each lesson's review status, and run review and build. The notebook updates in place, and your practice progress is kept separately from the `output/notebook.html` file. Its Review section connects Claude: paste an API key (checked, then saved in the git-ignored `secrets.json`). Besides Claude, it can use any provider with an OpenAI-compatible API: OpenAI, Google Gemini, OpenRouter, Groq, Mistral, DeepSeek, or a local model in Ollama or LM Studio. Pick one, enter the model name and key, and `review` uses it too. Your transcripts go to that provider, and smaller models find fewer errors, or click **Connect Claude Desktop** to register the MCP server there (Claude Code picks up `.mcp.json` by itself). The Lessons screen also links to your Cambly and Preply lesson history, and has the optional automated extraction behind the same warning as the command line: you tick a box accepting the risk to your account each time, then log in to the platform in the Chrome window it opens. It only accepts connections from your own computer; press Ctrl+C in the terminal to stop it.

## Error types

Every reviewer uses the same nine types, defined in [`lessonreview/categories.py`](lessonreview/categories.py) with the rule, drills and plan tasks for each: prepositions, vocabulary and false friends, verb forms, tenses, subject-verb agreement, comparatives and adverbs, articles, can/can't (polarity), and other.

## Privacy

- Your lessons, reviews and notebook stay on your machine. `inbox/`, `raw/`, `analysis/`, `output/`, `manifest.json`, `config.json` and `.browser-profile/` are all in `.gitignore`.
- With the API or MCP review, lesson transcripts are sent to Anthropic to be reviewed. The offline review sends nothing anywhere.
- The `examples/` data comes from one learner, with tutor names, companies and places removed.

## Disclaimer

This project is not affiliated with Cambly or Preply. The supported workflow only reads text you copied yourself from your own lessons, for personal study; Cambly's terms allow downloading content for personal use. The optional automated extractor is against both platforms' terms (see above); use it only if you accept the risk to your account. Page layouts change, so the parsers may need updates: they live in [`lessonreview/extract/parse.py`](lessonreview/extract/parse.py) and [`lessonreview/importer.py`](lessonreview/importer.py), with tests in [`tests/`](tests/).

## Development

```bash
pip install -r requirements.txt pytest
python -m pytest
```

## License

Public domain ([Unlicense](LICENSE)). Use it however you like.
