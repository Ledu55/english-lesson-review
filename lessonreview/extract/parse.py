"""Turn page text (lists of lines) into raw-lesson fields. Pure functions: no browser needed, easy to test.

Labels are matched in English and Portuguese, since the platforms render in the account's interface language.
"""
import re


def _is(line, *labels):
    return re.fullmatch("|".join(labels), line.strip().rstrip(":"), flags=re.I) is not None


def _after(lines, i, labels):
    """Index of the next line matching labels, starting at i."""
    for j in range(i, len(lines)):
        if _is(lines[j], *labels):
            return j
    return -1


def _num(s):
    m = re.search(r"\d+", s.replace(",", ""))
    return int(m.group()) if m else None


# --- Cambly -----------------------------------------------------------------

C_SAID = (r"you said", r"você disse")
C_SUGG = (r"suggestion", r"sugestão")
C_EXPL = (r"explanation", r"explicação")
C_WELL = (r"what you'?re doing well", r"o que você está fazendo bem")
C_CATS = {"grammar": "grammar", "gramática": "grammar", "vocabulary": "vocabulary", "vocabulário": "vocabulary",
          "fluency": "fluency", "fluência": "fluency", "pronunciation": "pronunciation", "pronúncia": "pronunciation"}
C_PENDING = re.compile(r"preparing your|preparando sua", re.I)


def cambly_header(lines):
    """Tutor, talk %, WPM, unique words and minutes from the lesson page header."""
    out = {}
    try:
        i = next(k for k, s in enumerate(lines) if _is(s, "chat"))
        out["tutor"] = lines[i + 1]
    except (StopIteration, IndexError):
        pass
    for k, s in enumerate(lines[:-1]):
        nxt = lines[k + 1]
        if re.search(r"talk (time|percentage)|porcentagem de conversação", s, re.I):
            out["talk_pct"] = _num(nxt)
        elif re.search(r"words per minute|palavras por minuto", s, re.I):
            out["wpm"] = _num(nxt)
        elif re.search(r"unique words|palavras exclusivas", s, re.I):
            out["unique_words"] = _num(nxt)
        elif re.fullmatch(r"\d+ (minutes|minutos)", s, re.I) and "duration_min" not in out:
            out["duration_min"] = _num(s)
    return out


def cambly_feedback(lines):
    """[{tag, original, correction, explanation}] and strengths [{tag:'strength', text, explanation}]."""
    items, i = [], 0
    while i < len(lines):
        s = lines[i]
        if _is(s, *C_SAID) and i + 1 < len(lines):
            tag = C_CATS.get(lines[i - 1].strip().lower(), "grammar") if i else "grammar"
            item = {"tag": tag, "original": lines[i + 1], "correction": "", "explanation": ""}
            j = _after(lines, i + 2, C_SUGG)
            if 0 <= j < i + 6 and j + 1 < len(lines):
                item["correction"] = lines[j + 1]
                k = _after(lines, j + 2, C_EXPL)
                if 0 <= k < j + 5 and k + 1 < len(lines):
                    item["explanation"] = lines[k + 1]
            if item["correction"]:
                items.append(item)
            i += 2
            continue
        if _is(s, *C_WELL) and i + 1 < len(lines):
            item = {"tag": "strength", "text": lines[i + 1], "explanation": ""}
            k = _after(lines, i + 2, C_EXPL)
            if 0 <= k < i + 4 and k + 1 < len(lines):
                item["explanation"] = lines[k + 1]
            items.append(item)
        i += 1
    return items


def cambly_pending(lines):
    return any(C_PENDING.search(s) for s in lines)


# --- Preply -----------------------------------------------------------------

P_SAID = (r"you said", r"você disse")
P_CORR = (r"correction", r"correção")
P_RECUR = (r"recurring", r"recorrente")
P_TALK = re.compile(r"talk time|tempo de conversação", re.I)
P_TOPIC = (r"topic of the day", r"tema do dia")
P_VOCAB = (r"key vocabulary", r"vocabulário-chave")
LEVEL = re.compile(r"^(A1|A2|B1|B2|C1|C2)\s*•\s*(.+)$")


def preply_feedback(lines):
    items, seen = [], set()
    for i, s in enumerate(lines):
        if not _is(s, *P_SAID) or i + 3 >= len(lines) or not _is(lines[i + 2], *P_CORR):
            continue
        orig = lines[i + 1].lstrip(".… ").strip()  # Preply prefixes excerpts with "..."
        corr = lines[i + 3]
        rest = lines[i + 4:i + 8]
        tag = rest[0] if rest and not _is(rest[0], *P_SAID) else "grammar"
        expl_lines = [x for x in rest[1:] if not _is(x, *P_RECUR) and not _is(x, *P_SAID)]
        expl = expl_lines[0] if expl_lines and len(expl_lines[0]) > 25 else ""
        key = (orig.lower(), corr.lower())
        if key not in seen:
            seen.add(key)
            items.append({"tag": tag, "original": orig, "correction": corr, "explanation": expl})
    return items


def preply_header(lines):
    out = {}
    for i, s in enumerate(lines):
        if P_TALK.search(s):
            vals = [lines[j] for j in range(i + 1, min(i + 8, len(lines))) if re.search(r"\d+ min", lines[j])]
            if vals:  # the learner's value comes first, under "You"
                out["learner_min"] = _num(vals[0])
                m = re.search(r"\((\d+)%\)", vals[0])
                out["talk_pct"] = int(m.group(1)) if m else None
            break
    j = _after(lines, 0, P_TOPIC)
    if 0 <= j < len(lines) - 1:
        out["topic"] = lines[j + 1]
    return out


def preply_vocabulary(lines):
    words, seen = [], set()
    start = _after(lines, 0, P_VOCAB)
    if start < 0:
        return words
    for i in range(start + 1, len(lines) - 1):
        m = LEVEL.match(lines[i + 1])
        if m and lines[i] not in seen:
            seen.add(lines[i])
            words.append(f"{lines[i]} ({m.group(1)}, {m.group(2)})")
    return words
