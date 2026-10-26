"""Merge every lesson review and the raw lesson stats into analysis/errors.json."""
from . import config, rawfile


def run():
    reviews = sorted((config.read_json(p) for p in config.REVIEWS.glob("*.json")),
                     key=lambda r: (r.get("lesson") or "", r["file"]))
    errors, vocabulary, strengths, seen_vocab = [], [], [], set()
    for r in reviews:
        for e in r["errors"]:
            errors.append({"id": f"e{len(errors) + 1:03d}", "lesson": r["lesson"], "source": r["source"], **e})
        for v in r["vocabulary"]:
            key = (v["wrong"].lower(), v["right"].lower())
            if key not in seen_vocab:
                seen_vocab.add(key)
                vocabulary.append(v)
        strengths += [{"lesson": r["lesson"], "text": s} for s in r["strengths"]]

    stats = []
    for p in sorted(config.RAW.glob("*.md")):
        m = rawfile.parse(p)["meta"]
        stats.append({"lesson": m.get("date"), "source": m.get("source"), "tutor": m.get("tutor") or "",
                      "talk": m.get("talk_pct"), "wpm": m.get("wpm"), "unique": m.get("unique_words"),
                      "learner_min": m.get("learner_min"), "minutes": m.get("duration_min"), "topic": m.get("topic")})

    data = {"reviewed_lessons": [r["file"] for r in reviews], "errors": errors, "vocabulary": vocabulary,
            "strengths": strengths, "stats": stats}
    config.write_json(config.ERRORS, data)
    print(f"analysis/errors.json: {len(errors)} errors from {len(reviews)} lessons")
    return data
