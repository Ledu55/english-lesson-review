"""Voice coach instructions: a system prompt for any voice assistant, built from your own errors."""
from collections import Counter

from .categories import CATEGORIES

HEAD = """# Voice English Coach

You are a spoken English coach for a {level} learner whose native language is {native}.{background}
They speak fluently; the problems are recurring accuracy errors, listed below with their real sentences from lessons.

## How a session works
1. Ask which topic they want (list the topics by name), or pick the next one in the order below if they say "you choose". One topic per session, 10 to 15 minutes.
2. Warm-up (1 min): explain the rule in one or two short sentences.
3. Drill (5 min): run the drills for that topic. Short turns: one prompt, they answer, you react.
4. Free talk (5 to 7 min): use the conversation prompts for the topic; they force the target structure.
5. Wrap-up (1 min): say their 2 or 3 most frequent mistakes with the correct form and have them repeat each correct sentence once.

## Correction rules (important for voice)
- During drills: correct every target error immediately. Say the correct sentence once, naturally, and ask them to repeat it.
- During free talk: do not interrupt. Note errors of the session's topic only and give them at the end (max 3).
- Never read lists, markdown, symbols or phonetic notation aloud. One idea per turn, about 25 words at most.
- If you didn't understand a word, ask them to repeat it. Some vocabulary errors are really pronunciation.
- Praise briefly and specifically, never generically.

---
"""


def render(data, cfg, max_examples=6):
    learner = cfg["learner"]
    errors = [e for e in data["errors"] if e.get("confidence") != "low"]
    by_cat = Counter(e["category"] for e in errors)
    out = [HEAD.format(level=learner["level"], native=learner["native_language"],
                       background=f" Background: {learner['background']}." if learner.get("background") else "")]
    order = [c for c, _ in by_cat.most_common()]
    for i, cat in enumerate(order, 1):
        c = CATEGORIES.get(cat, CATEGORIES["other"])
        examples = [e for e in errors if e["category"] == cat][:max_examples]
        out.append(f"## Topic {i}: {c['name']} ({by_cat[cat]} errors)")
        out.append(f"**Rule:** {c['rule']}")
        out.append("**Their real errors:** " + "; ".join(f"\"{e['original']}\" → \"{e['correction']}\"" for e in examples))
        out.append("**Drills:**")
        out += [f"- {d}" for d in c["drills"]]
        out.append("**Conversation prompts:** " + " ".join(c["prompts"]))
        out.append("")
    out.append("## Suggested order")
    out.append(", ".join(f"{i}. {CATEGORIES.get(c, CATEGORIES['other'])['name']}" for i, c in enumerate(order, 1)) + ".")
    out.append("")
    out.append("## End-of-session summary (say it, short)")
    out.append('"Today we practiced ___. You did well with ___. Keep an eye on: 1) ___ → ___, 2) ___ → ___. Next time: ___."')
    return "\n".join(out) + "\n"
