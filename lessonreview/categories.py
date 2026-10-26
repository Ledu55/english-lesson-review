"""Error categories: the single source for names, colors, rules, drills and plan tasks.

Every reviewer (LLM, MCP host or offline) must use one of these keys. The notebook,
the weekly plan and the voice coach are all generated from this table.
"""

CATEGORIES = {
    "prepositions": {
        "name": "Prepositions",
        "hint": "on/in/at for time and place, by for means, for/about/at after verbs.",
        "color": "#2F6FD6",
        "rule": "on + day (on Monday), in + part of the day (in the evening), at + clock time (at 5:30). "
                "Transport: by car, on foot. Fixed verb + preposition pairs: look at, pay for, work on, think about.",
        "drills": [
            "Time rapid-fire: the coach says a day, time or part of the day; the learner makes a sentence about their routine.",
            "Ask how the learner gets to work, the gym or a friend's place; expect by car / on foot / by bus.",
            "The coach says a verb (look, pay, work, think, aim, depend); the learner uses it with the right preposition.",
        ],
        "prompts": [
            "Describe your weekly routine day by day.",
            "Walk me through a typical Monday from waking up to going to bed.",
        ],
        "tasks": [
            "on / in / at with days, parts of the day and clock times",
            "by / on with transport: by car, on foot",
            "Verb + preposition pairs from your error list (look at, work on, think about)",
            "Say 10 sentences aloud each day; reread your preposition errors",
        ],
    },
    "vocabulary": {
        "name": "Vocabulary & false friends",
        "hint": "The word exists, but it doesn't mean what you meant.",
        "color": "#B5479B",
        "rule": "False friends look like a word in your language but mean something else. Some 'vocabulary' errors are "
                "pronunciation: the transcript heard a different word.",
        "drills": [
            "The coach says a word in the learner's language; the learner gives the English word in a sentence.",
            "Minimal pairs from the error list: the coach says one word, the learner says which; then swap roles.",
        ],
        "prompts": [
            "Tell me about your family and relatives.",
            "How do you manage your team? What was your degree in?",
        ],
        "tasks": [
            "Make a card for each false friend in your error list and review it daily",
            "Minimal pairs from your list: record yourself saying both words",
            "Use 5 corrected words in new sentences of your own",
        ],
    },
    "verb-forms": {
        "name": "Verb forms",
        "hint": "Gerund vs. infinitive, a missing auxiliary (am/do), base form after to/didn't.",
        "color": "#D9822B",
        "rule": "After a preposition or as a complement use -ing (my job is talking, tired of sitting). Keep the auxiliary: "
                "I'm still working, I don't agree, I was born. Base form after didn't / to.",
        "drills": [
            "Complete aloud: 'Most of my job is ___', 'I'm tired of ___', 'Before ___, I ___', 'Do you mind ___?'",
            "Quick negatives: the coach makes a statement, the learner disagrees in the negative.",
        ],
        "prompts": [
            "What does a normal workday consist of?",
            "What are you tired of doing at work?",
        ],
        "tasks": [
            "Gerund after prepositions and after like / mind / be used to",
            "Missing auxiliaries: I'm still ..., I don't ..., I was born",
            "Base form after didn't and to",
        ],
    },
    "tenses": {
        "name": "Tenses",
        "hint": "Past narrative, present perfect with since, no will/would after if.",
        "color": "#6A55C9",
        "rule": "Keep stories in the past. Since/for + a period up to now takes the present perfect. "
                "No will/would in the if-clause (if it were, not if it would be).",
        "drills": [
            "'How long have you...?' questions about work, home and studies; expect the present perfect.",
            "Second conditional: 'If you had more time / lived abroad, what would you do?'",
        ],
        "prompts": [
            "Tell your career story in 3 minutes without switching to the present tense.",
            "Tell me about a difficult project and how it ended.",
        ],
        "tasks": [
            "Tell a past story aloud and record it; check every verb",
            "Present perfect with since / for",
            "Conditionals: no will / would after if",
        ],
    },
    "subject-verb-agreement": {
        "name": "Subject-verb agreement",
        "hint": "He/she/it takes -s; a plural subject takes a plural verb.",
        "color": "#1E9A8A",
        "rule": "he / she / it / a singular noun takes verb + s (has, starts, doesn't). A plural subject takes a plural verb "
                "(were, don't, have), even when the subject is long.",
        "drills": [
            "The coach gives a subject (my manager, my colleagues, the team); the learner says what it usually does.",
            "Long-subject drill: 'All the projects we have for this client ...'; check the verb.",
        ],
        "prompts": [
            "Describe your current team and what each person does.",
            "Compare the tools your company uses.",
        ],
        "tasks": [
            "Third-person -s: has, starts, doesn't",
            "Plural subject + plural verb, especially with long subjects",
            "was / were in past descriptions",
        ],
    },
    "comparatives-adverbs": {
        "name": "Comparatives & adverbs",
        "hint": "fewer vs. less, no double comparatives, adjective vs. adverb.",
        "color": "#C24A4A",
        "rule": "fewer + countable (fewer people), less + uncountable (less time). No double comparatives "
                "(happier, not more happier). Adjective after be (it's easy), adverb to describe a verb (quickly).",
        "drills": [
            "The coach says a noun (meetings, money, people, stress); the learner says 'I'd like fewer/less ___'.",
            "Compare two things the coach names using three comparatives.",
        ],
        "prompts": [
            "How is your life different from five years ago?",
            "Compare working remotely and in the office.",
        ],
        "tasks": [
            "fewer (countable) vs. less (uncountable)",
            "Short adjectives take -er; no more + -er",
            "Adjective vs. adverb after be and with verbs",
        ],
    },
    "articles": {
        "name": "Articles",
        "hint": "a/an/the: when to use them and when to drop them.",
        "color": "#5E8F2E",
        "rule": "a/an only with singular countable nouns (an easy way, a holiday). No article with plurals and "
                "uncountables in general statements, or in fixed phrases: go to bed, go home, after work.",
        "drills": [
            "The coach says a noun phrase; the learner uses it in a sentence (easy way, holiday, bed, home, work).",
            "Describe yesterday from waking up to going to bed.",
        ],
        "prompts": [
            "How do people celebrate a national holiday where you live?",
            "Describe your company's infrastructure or product.",
        ],
        "tasks": [
            "a / an with singular countable nouns",
            "No article: go to bed, go home, after work, plural generalizations",
            "Holidays and abstract nouns without the",
        ],
    },
    "polarity": {
        "name": "Can / can't",
        "hint": "The meaning is negative, so the affirmative form flipped it.",
        "color": "#8A6D3B",
        "rule": "The meaning was negative but the sentence said can (or will). Say can't clearly: a longer vowel and an "
                "audible final t.",
        "drills": [
            "Yes/no questions about abilities; the learner answers with full sentences, half of them negative.",
            "Minimal pair: the learner says 'I can do it / I can't do it'; the coach reports which one was heard.",
        ],
        "prompts": [
            "What could you never give up?",
            "What can't AI replace in your job?",
        ],
        "tasks": [
            "Read your can/can't errors aloud, stressing can't",
            "Record 5 negative sentences and check they sound negative",
        ],
    },
    "other": {
        "name": "Other",
        "hint": "Plurals after numbers, uncountable nouns, fixed expressions.",
        "color": "#7A889B",
        "rule": "Plural after numbers (two scoops). effort, time and advice are uncountable (a lot of effort). "
                "Fixed expressions: in most cases, most of the year.",
        "drills": [
            "Quantity questions: 'How many meetings do you have a day?'",
            "Tag questions: 'It's been a long week, ___?'",
        ],
        "prompts": [
            "What does your company put the most effort into?",
            "Describe your diet in numbers.",
        ],
        "tasks": [
            "Plural after numbers; uncountable nouns (effort, time, advice)",
            "Fixed expressions from your error list",
        ],
    },
}

KEYS = list(CATEGORIES)


def name(key):
    return CATEGORIES.get(key, CATEGORIES["other"])["name"]
