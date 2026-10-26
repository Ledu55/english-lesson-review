"""Diagnosis and weekly plan, computed from errors.json. No LLM involved."""
from collections import Counter

from .categories import CATEGORIES, name

PLAN_WEEKS = 4


def _usable(errors):
    return [e for e in errors if e.get("confidence") != "low"]


def _quote(s, n=48):
    s = s.strip()
    return f"“{s if len(s) <= n else s[:n - 1] + '…'}”"


def diagnosis(data):
    errors = data["errors"]
    by_cat = Counter(e["category"] for e in errors)
    lessons = sorted({(e["lesson"], e["source"]) for e in errors} |
                     {(s["lesson"], s["source"]) for s in data.get("stats", [])})

    notes = {}
    for cat in by_cat:
        examples = [e["original"] for e in errors if e["category"] == cat and e.get("confidence") != "low"][:2]
        notes[cat] = ", ".join(_quote(x) for x in examples) or CATEGORIES.get(cat, CATEGORIES["other"])["hint"]

    evo = {}
    for lesson, source in lessons:
        here = Counter(e["category"] for e in errors if e["lesson"] == lesson and e["source"] == source)
        top = ", ".join(name(c).lower() for c, _ in here.most_common(2))
        evo[lesson] = f"{sum(here.values())} corrections" + (f", mostly {top}" if top else "")

    findings = []
    if len(lessons) >= 4:
        half = len(lessons) // 2
        first, last = set(lessons[:half]), set(lessons[half:])
        n1 = sum(1 for e in errors if (e["lesson"], e["source"]) in first) / len(first)
        n2 = sum(1 for e in errors if (e["lesson"], e["source"]) in last) / len(last)
        trend = "down" if n2 < n1 * 0.85 else "up" if n2 > n1 * 1.15 else "about the same"
        findings.append(f"Corrections per lesson went {trend}: {n1:.1f} in the first half of the period, "
                        f"{n2:.1f} in the second. Counts also depend on how long you talked and on the topic.")
        third = max(1, len(lessons) // 3)
        early = {e["category"] for e in errors if (e["lesson"], e["source"]) in set(lessons[:third])}
        late = {e["category"] for e in errors if (e["lesson"], e["source"]) in set(lessons[-third:])}
        persistent = [name(c).lower() for c, _ in by_cat.most_common() if c in early & late][:3]
        if persistent:
            findings.append("Present from the first lessons to the last: " + ", ".join(persistent) + ".")
    if by_cat:
        top3 = by_cat.most_common(3)
        share = round(sum(n for _, n in top3) / len(errors) * 100)
        findings.append(f"Your top 3 error types ({', '.join(name(c).lower() for c, _ in top3)}) "
                        f"are {share}% of all corrections. Fixing those moves the needle most.")

    seen, strengths = set(), []
    for s in sorted(data.get("strengths", []), key=lambda s: s["lesson"], reverse=True):
        key = s["text"].lower()[:60]
        if key not in seen:
            seen.add(key)
            strengths.append(s["text"])
    sources = {s for _, s in lessons}
    return {
        "strengths": strengths[:5],
        "notes": notes,
        "evo": evo,
        "findings": findings,
        "preply": ("Preply lessons have partial data: the AI summary and its corrections, no full transcript. "
                   "Compare error types across platforms, not counts.") if "preply" in sources else "",
        "confidence": "Low-confidence items may be transcription artifacts. They appear in the error list "
                      "but are left out of flashcards and exercises.",
    }


def plan(data):
    by_cat = Counter(e["category"] for e in _usable(data["errors"]))
    weeks = []
    for i, (cat, n) in enumerate(by_cat.most_common(PLAN_WEEKS)):
        c = CATEGORIES.get(cat, CATEGORIES["other"])
        weeks.append({"title": f"Week {i + 1}", "focus": c["name"], "category": cat, "count": n,
                      "tasks": c["tasks"] + ["Do the daily review in the notebook every day this week"]})
    return weeks
