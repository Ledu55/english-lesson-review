"""The per-lesson review format, shared by the API reviewer, the MCP server and the offline reviewer."""
from .categories import KEYS

REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "errors": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "enum": KEYS},
                    "original": {"type": "string", "description": "The learner's words, verbatim from the transcript."},
                    "correction": {"type": "string", "description": "The corrected sentence or phrase."},
                    "explanation": {"type": "string", "description": "One or two sentences, in the explanation language."},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                },
                "required": ["category", "original", "correction", "explanation", "confidence"],
                "additionalProperties": False,
            },
        },
        "strengths": {"type": "array", "items": {"type": "string"}},
        "vocabulary": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "wrong": {"type": "string"},
                    "right": {"type": "string"},
                    "note": {"type": "string"},
                },
                "required": ["wrong", "right", "note"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["errors", "strengths", "vocabulary"],
    "additionalProperties": False,
}


def validate(review):
    """Return a cleaned copy of review or raise ValueError listing every problem."""
    problems = []
    if not isinstance(review, dict):
        raise ValueError("review must be an object with errors, strengths and vocabulary")
    errors = review.get("errors")
    if not isinstance(errors, list):
        problems.append("errors must be a list")
        errors = []
    clean = []
    for i, e in enumerate(errors):
        if not isinstance(e, dict):
            problems.append(f"errors[{i}] must be an object")
            continue
        for f in ("original", "correction", "explanation"):
            if not isinstance(e.get(f), str) or not e[f].strip():
                problems.append(f"errors[{i}].{f} must be a non-empty string")
        if e.get("category") not in KEYS:
            problems.append(f"errors[{i}].category must be one of {KEYS}")
        if e.get("confidence") not in ("high", "medium", "low"):
            problems.append(f"errors[{i}].confidence must be high, medium or low")
        clean.append({k: (e.get(k) or "").strip() for k in ("category", "original", "correction", "explanation", "confidence")})
    strengths = review.get("strengths", [])
    if not isinstance(strengths, list) or not all(isinstance(s, str) for s in strengths):
        problems.append("strengths must be a list of strings")
        strengths = []
    vocab = review.get("vocabulary", [])
    if not isinstance(vocab, list):
        problems.append("vocabulary must be a list")
        vocab = []
    clean_vocab = []
    for i, v in enumerate(vocab):
        if not isinstance(v, dict) or not all(isinstance(v.get(k), str) for k in ("wrong", "right")):
            problems.append(f"vocabulary[{i}] needs string fields wrong and right")
            continue
        clean_vocab.append({"wrong": v["wrong"].strip(), "right": v["right"].strip(), "note": str(v.get("note") or "").strip()})
    if problems:
        raise ValueError("; ".join(problems))
    return {"errors": clean, "strengths": [s.strip() for s in strengths if s.strip()], "vocabulary": clean_vocab}
