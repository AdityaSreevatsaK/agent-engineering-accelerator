"""Framework-independent parts of the policy Q&A example: the policy corpus, retrieval, grading and the model double.

The model is simulated. The double is a deterministic rule engine that reads the system prompt it receives and
applies only the behaviour rules that prompt states: each rule is one sentence of the prompt (RULE_SENTENCES). So a
prompt edit that drops or adds a sentence changes what the double does, which is how the confident prompt causes a
regression offline. Policy figures come only from search_policy; the double's own beliefs (PRIOR_BELIEFS) are what a
model "knows" without retrieval, and one of them is wrong on purpose.
"""

import json
import re
from dataclasses import dataclass
from typing import Any

MAX_REWRITES = 2


@dataclass(frozen=True)
class Chunk:
    section: str
    title: str
    text: str
    keywords: frozenset[str]  # topic terms the grader accepts as relevant


CORPUS: tuple[Chunk, ...] = (
    Chunk(
        "TRV-1.1",
        "Booking",
        "All business travel must be booked through the corporate travel portal at least 14 days before departure.",
        frozenset({"book", "booked", "booking", "portal", "advance"}),
    ),
    Chunk(
        "TRV-2.3",
        "Air travel class",
        "Economy class is required for flights under 6 hours; business class is allowed for flights of 6 hours "
        "or more.",
        frozenset({"fly", "flight", "flights", "airfare", "economy"}),
    ),
    Chunk(
        "TRV-3.1",
        "Rail travel",
        "Standard class rail fares are reimbursed; first class is reimbursed only when it is cheaper than standard.",
        frozenset({"rail", "train", "trains"}),
    ),
    Chunk(
        "TRV-4.2",
        "Hotel accommodation",
        "The nightly hotel cap is USD 250 in tier 1 cities (London, New York, Paris, Tokyo) and USD 180 in all other "
        "cities, excluding taxes.",
        frozenset({"hotel", "hotels", "lodging"}),
    ),
    Chunk(
        "TRV-5.1",
        "Ground transport",
        "Taxis and ride-hailing are reimbursed up to USD 60 per journey; keep the receipt.",
        frozenset({"taxi", "taxis", "ride-hailing"}),
    ),
    Chunk(
        "EXP-2.1",
        "Meals",
        "The meal per diem is USD 75 per day for domestic travel and USD 95 per day for international travel.",
        frozenset({"meal", "meals", "diem", "food"}),
    ),
    Chunk(
        "EXP-3.4",
        "Alcohol",
        "Alcohol is not reimbursable under any circumstances.",
        frozenset({"alcohol", "wine", "beer"}),
    ),
    Chunk(
        "EXP-4.1",
        "Receipts",
        "Itemised receipts are required for every expense over USD 25.",
        frozenset({"receipt", "receipts", "itemised"}),
    ),
    Chunk(
        "EXP-6.2",
        "Submission deadline",
        "Expense reports must be submitted within 30 days of the end of the trip.",
        frozenset({"deadline", "submit", "submitted", "submission"}),
    ),
    Chunk(
        "EXP-7.1",
        "Mileage",
        "Business use of a personal car is reimbursed at USD 0.67 per mile.",
        frozenset({"mileage", "mile", "miles", "car", "drive"}),
    ),
)

STOPWORDS = frozenset(
    "a an and are be can do does for from how i in is it many may much must my of on or per the to what when "
    "where which while who will with".split()
)
# The query rewriter's vocabulary: everyday words mapped to the policy's terms.
SYNONYMS: dict[str, str] = {"cab": "taxi", "uber": "ride-hailing", "booze": "alcohol", "dinner": "meal"}
SEARCH_LIMIT = 2

# One prompt sentence per behaviour rule. The double applies a rule only if its sentence appears in the system prompt.
RULE_SENTENCES: dict[str, str] = {
    "always_search": "Always search the policy with search_policy before answering.",
    "confident": "Answer directly when you are confident of the answer.",
    "cite": "Cite the section id of the policy text you used, in square brackets.",
    "not_covered": "If nothing relevant is found, say it is not covered by policy.",
}

_INTRO = "You answer employee questions about the travel and expense policy. "
_FORMAT = " Quote the policy figure exactly and answer in one or two sentences."

PROMPT = _INTRO + " ".join(RULE_SENTENCES[r] for r in ("always_search", "cite", "not_covered")) + _FORMAT

# A plausible latency tweak: skip the search round trip when the model already knows. The always-search rule goes.
PROMPT_CONFIDENT = _INTRO + " ".join(RULE_SENTENCES[r] for r in ("confident", "cite", "not_covered")) + _FORMAT

# What the double "knows" without retrieval: topic term to a belief. The hotel figure is invented (the policy says
# USD 250 or USD 180), which is the hallucination the confident prompt lets through.
PRIOR_BELIEFS: dict[str, str] = {
    "hotel": "Hotels are capped at USD 300 per night.",
    "hotels": "Hotels are capped at USD 300 per night.",
}

NOT_COVERED = "This is not covered by policy."
NOT_FOUND = "I could not find that in the policy."
ANSWER_HEADER = "Answer the employee's question using only these policy extracts."
NO_EXTRACTS = "No relevant policy text was found."


def terms(text: str) -> list[str]:
    """Lower-case content words in order, without stopwords or duplicates."""
    words = re.findall(r"[a-z0-9]+(?:[-.][a-z0-9]+)*", text.lower())
    return list(dict.fromkeys(w for w in words if w not in STOPWORDS))


def _score(wanted: set[str], chunk: Chunk) -> int:
    """Topic terms count double, so a chunk about the topic outranks one that merely mentions a query word."""
    return 2 * len(wanted & chunk.keywords) + len(wanted & set(terms(chunk.text)))


# Tool logic.
def search_policy(query: str) -> str:
    """Keyword search: chunks sharing any term with the query, best score first (ties by section id), as JSON."""
    wanted = set(terms(query))
    scored = [(_score(wanted, c), c) for c in CORPUS]
    hits = sorted((pair for pair in scored if pair[0] > 0), key=lambda pair: (-pair[0], pair[1].section))
    return json.dumps([{"section": c.section, "title": c.title, "text": c.text} for _, c in hits[:SEARCH_LIMIT]])


# Grader and rewriter (plain code in both the offline and the live agent).
def relevant_chunks(query: str, results: list[str]) -> list[dict[str, Any]]:
    """Retrieved chunks whose topic terms appear in the query, in retrieval order. A text-only match is not enough."""
    wanted = set(terms(query))
    by_section = {c.section: c for c in CORPUS}
    relevant: list[dict[str, Any]] = []
    for result in results:
        try:
            chunks = json.loads(result)
        except json.JSONDecodeError:
            continue
        for chunk in chunks if isinstance(chunks, list) else []:
            known = by_section.get(chunk.get("section", "")) if isinstance(chunk, dict) else None
            if known is not None and wanted & known.keywords and chunk not in relevant:
                relevant.append(chunk)
    return relevant


def rewrite_query(question: str) -> str:
    """Drop stopwords and map everyday words to policy terms."""
    return " ".join(SYNONYMS.get(term, term) for term in terms(question))


# The header and the question label together, so a question that merely starts with the header is not a request.
_REQUEST_PREFIX = f"{ANSWER_HEADER}\nQuestion: "


def answer_request(question: str, chunks: list[dict[str, Any]]) -> str:
    extracts = json.dumps(chunks) if chunks else NO_EXTRACTS
    return f"{_REQUEST_PREFIX}{question}\nExtracts: {extracts}"


def parse_answer_request(text: str) -> list[dict[str, Any]] | None:
    """The extracts from an answer request; None when text is not one."""
    if not text.startswith(_REQUEST_PREFIX):
        return None
    extracts = text.rsplit("\nExtracts: ", 1)[-1]
    return [] if extracts == NO_EXTRACTS else json.loads(extracts)


# The model double.
@dataclass(frozen=True)
class Search:
    query: str


def active_rules(system_prompt: str) -> set[str]:
    return {rule for rule, sentence in RULE_SENTENCES.items() if sentence in system_prompt}


def decide(system_prompt: str, query: str, searched: bool) -> Search | str:
    """First step for a query: search, or answer from belief when the prompt allows it and the double is confident."""
    rules = active_rules(system_prompt)
    if "always_search" not in rules and "confident" in rules and not searched:
        belief = next((PRIOR_BELIEFS[t] for t in terms(query) if t in PRIOR_BELIEFS), None)
        if belief is not None:
            return belief
    return Search(query)


def answer(system_prompt: str, chunks: list[dict[str, Any]]) -> str:
    """Answer from the first relevant extract, quoting it; cite and say "not covered" only when the prompt says so."""
    rules = active_rules(system_prompt)
    if not chunks:
        return NOT_COVERED if "not_covered" in rules else NOT_FOUND
    first = chunks[0]
    return f"{first['text']} [{first['section']}]" if "cite" in rules else first["text"]
