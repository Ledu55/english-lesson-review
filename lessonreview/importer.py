"""Step 1 (recommended): import lessons you copied from the platform pages yourself.

For each lesson, save one .txt file in inbox/ with the page text (select all, copy, paste):
- Cambly: the lesson page with the FEEDBACK tab open, then the same page with the TRANSCRIPT tab open,
  both pasted into the same file.
- Preply: the lesson insights page, after clicking "See all grammar feedback" and "See all vocabulary".

Copied text has no speaker names, so transcript lines are saved as "?" (unknown speaker).
"""
import hashlib
import re
import sys
from datetime import date
from pathlib import Path

from . import config, rawfile
from .extract import parse

INBOX = config.ROOT / "inbox"

MONTHS = {m: i + 1 for i, names in enumerate([
    ("jan", "january", "janeiro"), ("feb", "fev", "february", "fevereiro"), ("mar", "march", "março", "marco"),
    ("apr", "abr", "april", "abril"), ("may", "mai", "maio"), ("jun", "june", "junho"), ("jul", "july", "julho"),
    ("aug", "ago", "august", "agosto"), ("sep", "set", "sept", "september", "setembro"),
    ("oct", "out", "october", "outubro"), ("nov", "november", "novembro"), ("dec", "dez", "december", "dezembro"),
]) for m in names}

TRANSCRIPT_HEAD = re.compile(r"^(transcript|transcrição)$", re.I)
TRANSCRIPT_SKIP = re.compile(r"^(skip to|pule para)", re.I)
FOOTER = re.compile(r"^(privacy policy|política de privacidade)$", re.I)


def detect_platform(lines):
    text = "\n".join(lines[:400]).lower()
    if re.search(r"você disse:|you said:|porcentagem de conversação|palavras por minuto|words per minute", text):
        return "cambly"
    if re.search(r"tempo de conversação|talk time|tema do dia|topic of the day|key vocabulary", text):
        return "preply"
    return None


def find_date(lines, cfg):
    """First date on the page: '8 de setembro de 2026', 'September 8, 2026', '24 de ago., 18:30', 'Aug 24'."""
    pats = [r"(\d{1,2}) de ([a-zç]+)\.? de (\d{4})", r"([a-z]+)\.? (\d{1,2}),? (\d{4})",
            r"(\d{1,2}) de ([a-zç]+)\.?,", r"\b([a-z]{3,9})\.? (\d{1,2})\b"]
    for line in lines[:120]:
        low = line.lower()
        for p in pats:
            m = re.search(p, low)
            if not m:
                continue
            g = m.groups()
            day, month = (g[0], g[1]) if g[0].isdigit() else (g[1], g[0])
            if month not in MONTHS:
                continue
            year = int(g[2]) if len(g) > 2 else _guess_year(MONTHS[month], int(day), cfg)
            try:
                return date(year, MONTHS[month], int(day)).isoformat()
            except ValueError:
                continue
    return None


def _guess_year(month, day, cfg):
    """Preply omits the year: take the year that puts the date inside the configured period."""
    start, end = cfg["period"]["from"], cfg["period"]["to"]
    for year in range(int(end[:4]), int(start[:4]) - 1, -1):
        if start <= date(year, month, day).isoformat() <= end:
            return year
    return date.today().year


def cambly_transcript(lines):
    # The tab label is also "TRANSCRIPT"; the real heading is the one followed by "Skip to ..." (or the last one).
    heads = [i for i, s in enumerate(lines) if TRANSCRIPT_HEAD.match(s)]
    if not heads:
        return []
    start = next((i for i in heads if i + 1 < len(lines) and TRANSCRIPT_SKIP.match(lines[i + 1])), heads[-1])
    out = []
    for s in lines[start + 1:]:
        if FOOTER.match(s):
            break
        if not TRANSCRIPT_SKIP.match(s):
            out.append(("?", s))
    return out


def preply_tutor(lines):
    for s in lines[:80]:
        m = re.match(r"^(?:english|inglês|ingles),\s*(.+)$", s, re.I)
        if m:
            return m.group(1).strip()
    return None


def import_file(path, cfg, manifest, platform=None, day=None):
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = [s.strip() for s in text.splitlines() if s.strip()]
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]
    if any(l.get("id") == f"import-{digest}" for l in manifest["lessons"]):
        return None, "already imported"
    platform = platform or detect_platform(lines)
    if not platform:
        return None, "can't tell if this is a Cambly or Preply page; pass --platform"
    day = day or find_date(lines, cfg)
    if not day:
        return None, "no lesson date found; pass --date YYYY-MM-DD"

    meta = {"source": platform, "id": f"import-{digest}", "date": day}
    if platform == "cambly":
        if parse.cambly_pending(lines):
            return None, "Cambly is still preparing this lesson's feedback; copy it again later"
        meta.update(parse.cambly_header(lines))
        feedback, vocab, transcript = parse.cambly_feedback(lines), [], cambly_transcript(lines)
    else:
        meta.update(parse.preply_header(lines), tutor=preply_tutor(lines))
        feedback, vocab, transcript = parse.preply_feedback(lines), parse.preply_vocabulary(lines), []
    if not feedback and not transcript:
        return None, "no corrections or transcript found in the pasted text"

    existing = {f.name for f in config.RAW.glob("*.md")}
    name = rawfile.filename(platform, day, existing)
    (config.RAW / name).write_text(rawfile.render(meta, feedback, vocab, transcript), encoding="utf-8")
    manifest["lessons"].append({"source": platform, "id": meta["id"], "date": day, "tutor": meta.get("tutor"),
                                "file": name, "status": "done", "method": "import", "imported_from": path.name})
    return name, f"{len(feedback)} corrections, {len(transcript)} transcript lines"


def run(args, cfg):
    targets = [Path(p) for p in args.files] if args.files else [INBOX]
    files = []
    for t in targets:
        files += sorted(t.glob("*.txt")) if t.is_dir() else [t]
    if not files:
        INBOX.mkdir(exist_ok=True)
        sys.exit(f"No .txt files to import. Paste each lesson's page text into a .txt file in {INBOX}.")
    config.RAW.mkdir(exist_ok=True)
    manifest = config.read_json(config.MANIFEST, {"lessons": []})
    imported = 0
    for f in files:
        name, msg = import_file(f, cfg, manifest, args.platform, args.date)
        print(f"{f.name}: {'-> ' + name + ' (' + msg + ')' if name else 'skipped, ' + msg}")
        imported += bool(name)
        config.write_json(config.MANIFEST, manifest)
    print(f"Imported {imported} of {len(files)} files.")
