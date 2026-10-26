"""The raw lesson format: one Markdown file per lesson, written by the extractors.

    # Cambly lesson - 2026-08-25 08:30
    - source: cambly
    - id: 64f...
    - tutor: Alex
    - talk_pct: 64
    ...

    ## Platform feedback
    - [grammar] "I spent a time" -> "I spent some time" :: 'Time' is uncountable here.
    - [strength] You used past tenses well.

    ## Key vocabulary
    - taboo (B2, Noun)

    ## Transcript
    L: Learner line
    T: Tutor line
    ?: Line from copied text, speaker unknown

Anyone can also write these files by hand (see examples/raw/).
"""
import re
from pathlib import Path

HEADER_KEYS = ["source", "id", "date", "time", "tutor", "duration_min", "talk_pct", "wpm",
               "unique_words", "learner_min", "topic"]
NUMERIC = {"duration_min", "talk_pct", "wpm", "unique_words", "learner_min"}

FEEDBACK_RE = re.compile(r'^- \[(?P<tag>[^\]]+)\]\s*(?:"(?P<orig>.*?)"\s*->\s*"(?P<corr>.*?)"|(?P<text>.*?))\s*(?:::\s*(?P<expl>.*))?$')


def filename(source, date, existing=()):
    base = f"{source}_lesson_{date}"
    name, n = f"{base}.md", 2
    while name in existing:
        name, n = f"{base}_{n}.md", n + 1
    return name


def render(meta, feedback=(), vocabulary=(), transcript=(), notes=""):
    """meta: dict with HEADER_KEYS. feedback: dicts {tag, original, correction, explanation} or {tag, text}.
    transcript: (speaker, text) pairs where speaker is 'L' (learner), 'T' (tutor) or '?' (unknown)."""
    title = f"# {meta['source'].capitalize()} lesson - {meta['date']} {meta.get('time') or ''}".rstrip()
    lines = [title]
    for k in HEADER_KEYS:
        if meta.get(k) not in (None, ""):
            lines.append(f"- {k}: {meta[k]}")
    lines += ["", "## Platform feedback"]
    if not feedback:
        lines.append("Not available.")
    for f in feedback:
        expl = f" :: {_one_line(f['explanation'])}" if f.get("explanation") else ""
        if f.get("original"):
            lines.append(f'- [{f["tag"]}] "{_one_line(f["original"])}" -> "{_one_line(f["correction"])}"{expl}')
        else:
            lines.append(f"- [{f['tag']}] {_one_line(f['text'])}{expl}")
    if vocabulary:
        lines += ["", "## Key vocabulary"] + [f"- {_one_line(v)}" for v in vocabulary]
    lines += ["", "## Transcript"]
    lines += [f"{s}: {_one_line(t)}" for s, t in transcript] or ["Not available."]
    if notes:
        lines += ["", "## Notes", notes]
    return "\n".join(lines) + "\n"


def _one_line(s):
    return re.sub(r"\s+", " ", str(s)).strip().replace('"', "'") if s else ""


def parse(path):
    """Return {'file', 'meta', 'feedback', 'vocabulary', 'transcript'} for a raw lesson file."""
    path = Path(path)
    meta, feedback, vocabulary, transcript, section = {}, [], [], [], None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            section = line[3:].strip().lower()
            continue
        if section is None:
            m = re.match(r"^- (\w+): (.*)$", line)
            if m and m.group(1) in HEADER_KEYS:
                k, v = m.group(1), m.group(2).strip()
                meta[k] = _num(v) if k in NUMERIC else v
        elif section == "platform feedback":
            m = FEEDBACK_RE.match(line)
            if m:
                feedback.append({k: (v or "").strip() for k, v in m.groupdict().items()})
        elif section == "key vocabulary" and line.startswith("- "):
            vocabulary.append(line[2:].strip())
        elif section == "transcript":
            m = re.match(r"^([LT?]): (.*)$", line)
            if m:
                transcript.append((m.group(1), m.group(2)))
    if "date" not in meta:
        m = re.search(r"(\d{4}-\d{2}-\d{2})", path.name)
        meta["date"] = m.group(1) if m else ""
    meta.setdefault("source", path.name.split("_")[0])
    return {"file": path.name, "meta": meta, "feedback": feedback, "vocabulary": vocabulary, "transcript": transcript}


def _num(v):
    try:
        return float(v) if "." in v else int(v)
    except ValueError:
        return None
