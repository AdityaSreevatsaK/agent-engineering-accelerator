import json
import os
import subprocess
import sys
import types
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from agent_accelerator.compare import load_results

REPO = Path(__file__).resolve().parents[2]
# The examples are imported from the repo root, as `aea` does when it loads --agent.
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from examples.policy_rag.agent import (  # noqa: E402
    LIVE_MODEL_ID,
    SimulatedPolicyModel,
    build_agent,
    build_confident_agent,
    build_live_agent,
)
from examples.policy_rag.rules import (  # noqa: E402
    ANSWER_HEADER,
    CORPUS,
    NO_EXTRACTS,
    NOT_COVERED,
    NOT_FOUND,
    PRIOR_BELIEFS,
    PROMPT,
    PROMPT_CONFIDENT,
    RULE_SENTENCES,
    Search,
    active_rules,
    answer,
    answer_request,
    decide,
    parse_answer_request,
    relevant_chunks,
    rewrite_query,
    search_policy,
)

DATASET = REPO / "examples" / "policy_rag" / "dataset.jsonl"
GOLDEN = REPO / "examples" / "policy_rag" / "golden.jsonl"
BY_SECTION = {c.section: c for c in CORPUS}
HOTEL_LEEDS = "How much can I spend on a hotel in Leeds?"
PET_BOARDING = "Is pet boarding reimbursed while I travel?"
# A question that happens to open with the answer header, as a user pasting the agent's own framing might write.
HEADER_QUESTION = f"{ANSWER_HEADER} What is the nightly hotel cap in London?"


def _hit(section):
    """The search payload for one corpus chunk."""
    chunk = BY_SECTION[section]
    return {"section": chunk.section, "title": chunk.title, "text": chunk.text}


def _cited(section):
    return f"{BY_SECTION[section].text} [{section}]"


def _sections(payload):
    return [hit["section"] for hit in json.loads(payload)]


def _run(make, question):
    """The search queries the agent made and its final reply."""
    messages = make().invoke({"messages": [HumanMessage(question)]})["messages"]
    queries = [call["args"]["query"] for m in messages if isinstance(m, AIMessage) for call in m.tool_calls]
    return queries, messages[-1].content


def _jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


# search_policy


def test_search_ranks_a_topic_term_match_above_chunks_that_only_mention_a_query_word():
    # "lodging" is a TRV-4.2 topic term absent from its text (score 2); "expense" is only in the text of EXP-4.1 and
    # EXP-6.2 (score 1 each). Unweighted, all three tie at 1 and the two EXP chunks win on section id.
    # Witness s41 search topic not doubled: `return 2 * len(` -> `return 1 * len(` (rules.py:136).
    assert _sections(search_policy("lodging expense")) == ["TRV-4.2", "EXP-4.1"]


def test_search_breaks_ties_by_section_id_and_returns_at_most_two_hits():
    # "usd" is in the text of five chunks and no chunk's topic terms, so all five score 1.
    # By section id the first two are EXP-2.1 and EXP-4.1; corpus order would give TRV-4.2 and TRV-5.1.
    # Witness s41 search ties in corpus order: `key=lambda pair: (-pair[0], pair[1].section)` ->
    # `key=lambda pair: -pair[0]` (rules.py:144). Witness s41 search limit: `hits[:SEARCH_LIMIT]` ->
    # `hits[:SEARCH_LIMIT + 1]` (rules.py:145).
    assert json.loads(search_policy("usd")) == [_hit("EXP-2.1"), _hit("EXP-4.1")]


@pytest.mark.parametrize("query", ["pet boarding", "what is it?"], ids=["no_shared_term", "only_stopwords"])
def test_search_returns_an_empty_list_when_no_chunk_shares_a_term(query):
    # Witness s41 search keeps zero scores (rules.py:144).
    assert search_policy(query) == "[]"


# relevant_chunks


def test_grader_drops_a_retrieved_chunk_that_matches_the_query_only_in_its_text():
    # Witness s41 grader accepts text matches: `known is not None and wanted & known.keywords and` ->
    # `known is not None and` (rules.py:161).
    results = [search_policy("lodging expense")]

    assert _sections(results[0]) == ["TRV-4.2", "EXP-4.1"]
    assert relevant_chunks("lodging expense", results) == [_hit("TRV-4.2")]


def test_grader_skips_a_result_that_is_not_json_and_keeps_retrieval_order():
    # A tool error reaches the grader as plain text; ToolNode(handle_tool_errors=True) reports it.
    # Witness s41 grader stops at invalid json (rules.py:158).
    results = ["Error: search failed", search_policy("alcohol"), search_policy("hotel")]

    assert relevant_chunks("alcohol hotel", results) == [_hit("EXP-3.4"), _hit("TRV-4.2")]


def test_grader_returns_a_chunk_retrieved_twice_only_once():
    # Witness s41 grader no dedup: `and chunk not in relevant:` -> `:` (rules.py:161).
    assert relevant_chunks("hotel", [search_policy("hotel"), search_policy("hotel")]) == [_hit("TRV-4.2")]


def test_grader_ignores_json_that_is_not_a_list_of_known_sections():
    # Witness s41 grader iterates non-list: `chunks if isinstance(chunks, list) else []` -> `chunks` (rules.py:159);
    # iterating the number 5 then raises TypeError.
    results = ['5', '{"section": "TRV-4.2"}', '[1, {"section": "XYZ-9", "text": "hotel"}, {"title": "Hotel"}]']

    assert relevant_chunks("hotel", results) == []


# rewrite_query


@pytest.mark.parametrize(
    ("question", "rewritten"),
    [
        ("Can I expense a cab from the airport?", "expense taxi airport"),
        ("Is an Uber OK after dinner?", "ride-hailing ok after meal"),
        ("Booze at the hotel", "alcohol at hotel"),
    ],
    ids=["cab_to_taxi", "uber_and_dinner", "booze"],
)
def test_rewrite_drops_stopwords_and_maps_everyday_words_to_policy_terms(question, rewritten):
    # Witness s41 rewrite no synonyms: `SYNONYMS.get(term, term) for term` -> `term for term` (rules.py:168).
    # Witness s41 rewrite keeps stopwords: `STOPWORDS - "a and are be can do"` -> `"a and are be do"` (rules.py:92).
    assert rewrite_query(question) == rewritten


def test_rewrite_of_a_question_made_only_of_stopwords_is_empty():
    # Witness s41 rewrite keeps stopwords: `for w in words if w not in STOPWORDS` -> `for w in words` (rules.py:131).
    assert rewrite_query("What is it, and how do I do it?") == ""


# decide


@pytest.mark.parametrize(
    ("prompt", "query", "searched", "step"),
    [
        (PROMPT, HOTEL_LEEDS, False, Search(HOTEL_LEEDS)),
        (PROMPT_CONFIDENT, HOTEL_LEEDS, False, PRIOR_BELIEFS["hotel"]),
        (PROMPT_CONFIDENT, HOTEL_LEEDS, True, Search(HOTEL_LEEDS)),
        (PROMPT_CONFIDENT, "Can I expense a taxi?", False, Search("Can I expense a taxi?")),
        (PROMPT + " " + RULE_SENTENCES["confident"], HOTEL_LEEDS, False, Search(HOTEL_LEEDS)),
        ("Answer employee questions.", HOTEL_LEEDS, False, Search(HOTEL_LEEDS)),
    ],
    ids=[
        "always_search",
        "confident_with_a_belief",
        "confident_after_a_search",
        "confident_without_a_belief",
        "always_search_overrides_confident",
        "no_rule",
    ],
)
def test_decide_answers_from_belief_only_when_confident_without_always_search_before_any_search(
    prompt, query, searched, step
):
    # Witnesses, all rules.py:197: s41 decide always_search ignored (drop `"always_search" not in rules and `);
    # s41 decide searched ignored (drop `and not searched`); s41 decide confident not required (drop
    # `and "confident" in rules`).
    assert decide(prompt, query, searched) == step


# answer


CHUNKS = [_hit("TRV-4.2"), _hit("EXP-2.1")]


@pytest.mark.parametrize(
    ("prompt", "chunks", "reply"),
    [
        (PROMPT, CHUNKS, _cited("TRV-4.2")),
        (RULE_SENTENCES["not_covered"], CHUNKS, BY_SECTION["TRV-4.2"].text),
        (PROMPT, [], NOT_COVERED),
        (RULE_SENTENCES["cite"], [], NOT_FOUND),
    ],
    ids=["cite", "no_cite_rule", "nothing_found_not_covered", "nothing_found_no_not_covered_rule"],
)
def test_answer_quotes_the_first_extract_citing_it_and_says_not_covered_only_when_the_prompt_says_so(
    prompt, chunks, reply
):
    # Witness s41 answer always cites: `if "cite" in rules else first["text"]` -> `if True else first["text"]`
    # (rules.py:210). Witness s41 answer always not covered: `if "not_covered" in rules else NOT_FOUND` ->
    # `if True else NOT_FOUND` (rules.py:208). Witness s41 answer last extract: `first = chunks[0]` ->
    # `first = chunks[-1]` (rules.py:209).
    assert answer(prompt, chunks) == reply


@pytest.mark.parametrize(
    ("question", "chunks", "parsed"),
    [
        ("Hotel cap?", CHUNKS, CHUNKS),
        ("Hotel cap?", [], []),
        (HEADER_QUESTION, CHUNKS, CHUNKS),
        (HEADER_QUESTION, [], []),
    ],
    ids=["extracts", "no_extracts", "header_question_extracts", "header_question_no_extracts"],
)
def test_answer_request_round_trips_its_extracts(question, chunks, parsed):
    # Witness s41 parse no empty case: `return [] if extracts == NO_EXTRACTS else json.loads(extracts)` ->
    # `return json.loads(extracts)` (rules.py:185). Witness s45 parse rejects a header question: `if not
    # text.startswith(_REQUEST_PREFIX):` -> `if not text.startswith(_REQUEST_PREFIX) or ANSWER_HEADER in
    # text[len(_REQUEST_PREFIX):]:` (rules.py:182), a fix that refuses the ambiguous case, fails both header ids.
    assert parse_answer_request(answer_request(question, chunks)) == parsed


@pytest.mark.parametrize(
    ("chunks", "extracts"),
    [(CHUNKS, json.dumps(CHUNKS)), ([], NO_EXTRACTS)],
    ids=["extracts", "no_extracts"],
)
def test_answer_request_is_the_header_then_the_question_then_the_extracts_one_per_line(chunks, extracts):
    # Witness s45 request question label dropped: `_REQUEST_PREFIX = f"{ANSWER_HEADER}\\nQuestion: "` ->
    # `_REQUEST_PREFIX = f"{ANSWER_HEADER}\\n"` (rules.py:172); the round trip above still passes.
    assert answer_request("Hotel cap?", chunks).split("\n") == [
        ANSWER_HEADER,
        "Question: Hotel cap?",
        f"Extracts: {extracts}",
    ]


@pytest.mark.parametrize(
    "text",
    ["What is the nightly hotel cap in London?", HEADER_QUESTION],
    ids=["plain_question", "question_starting_with_the_header"],
)
def test_text_that_is_not_an_answer_request_parses_to_none(text):
    # A question opening with the header has no "Extracts: " tail, so reading it as a request used to raise.
    # Witness s41 parse accepts any text: `if not text.startswith(_REQUEST_PREFIX):` -> `if False:` (rules.py:182).
    # Witness s45 parse header only: `if not text.startswith(_REQUEST_PREFIX):` ->
    # `if not text.startswith(ANSWER_HEADER):` (rules.py:182) raises JSONDecodeError on the header question.
    assert parse_answer_request(text) is None


# prompts and the model double


def test_confident_prompt_is_the_good_prompt_with_always_search_replaced_by_confident():
    # Witness s41 confident prompt drops not_covered: `("confident", "cite", "not_covered")` ->
    # `("confident", "cite")` (rules.py:113).
    assert active_rules(PROMPT) == {"always_search", "cite", "not_covered"}
    assert active_rules(PROMPT_CONFIDENT) == {"confident", "cite", "not_covered"}
    assert PROMPT_CONFIDENT.replace(RULE_SENTENCES["confident"], RULE_SENTENCES["always_search"]) == PROMPT


def test_model_double_behaviour_follows_the_system_prompt_it_is_given():
    # Witness s41 model ignores prompt: `system_prompt = next(str(m.content) for m in messages if isinstance(m,
    # SystemMessage))` -> `system_prompt = PROMPT` (agent.py:49).
    def reply(prompt):
        return SimulatedPolicyModel().invoke([SystemMessage(prompt), HumanMessage(HOTEL_LEEDS)])

    searching, confident = reply(RULE_SENTENCES["always_search"]), reply(RULE_SENTENCES["confident"])

    assert [call["args"] for call in searching.tool_calls] == [{"query": HOTEL_LEEDS}]
    assert (confident.tool_calls, confident.content) == ([], PRIOR_BELIEFS["hotel"])


# the agent


def test_agent_answer_quotes_the_retrieved_figure_and_cites_its_section():
    # Witness s41 answer node drops graded chunks: `rules.answer_request(question, _relevant(state["messages"]))` ->
    # `rules.answer_request(question, [])` (agent.py:107).
    queries, reply = _run(build_agent, "What is the nightly hotel cap in London?")

    assert queries == ["What is the nightly hotel cap in London?"]
    assert reply == _cited("TRV-4.2")


def test_agent_answers_a_question_that_starts_with_the_answer_header_by_searching_for_it():
    # The header words are not any chunk's topic terms, so "hotel" alone makes TRV-4.2 the only relevant hit.
    # Witness s45 parse header only (above): the decide step reads the question as an answer request and raises.
    queries, reply = _run(build_agent, HEADER_QUESTION)

    assert queries == [HEADER_QUESTION]
    assert reply == _cited("TRV-4.2")


def test_agent_rewrites_a_query_with_no_relevant_hit_and_answers_from_the_rewritten_search():
    # The first search hits only text mentions of "expense"; "cab" is not a policy term until rewritten to "taxi".
    # Witness s41 rewrite node passes query through: `HumanMessage(rules.rewrite_query(_current_query(state[` ->
    # `HumanMessage((_current_query(state[` (agent.py:102).
    queries, reply = _run(build_agent, "Can I expense a cab from the airport?")

    assert queries == ["Can I expense a cab from the airport?", "expense taxi airport"]
    assert reply == _cited("TRV-5.1")


def test_agent_stops_after_two_rewrites_and_says_the_question_is_not_covered():
    # "reimbursed" and "travel" are in the text of five chunks but no chunk's topic terms, so every search returns hits
    # and the grader rejects them all.
    # Witness s41 rewrite cap off by one: `rewrites >= MAX_REWRITES else` -> `rewrites > MAX_REWRITES else`
    # (agent.py:99).
    queries, reply = _run(build_agent, PET_BOARDING)

    assert _sections(search_policy("pet boarding reimbursed travel")) == ["EXP-2.1", "EXP-7.1"]
    assert queries == [PET_BOARDING, "pet boarding reimbursed travel", "pet boarding reimbursed travel"]
    assert reply == NOT_COVERED


def test_factories_differ_only_in_prompt_and_the_confident_one_answers_hotel_questions_from_belief():
    # Witness s41 confident factory good prompt: `_build(SimulatedPolicyModel(), PROMPT_CONFIDENT)` ->
    # `_build(SimulatedPolicyModel(), PROMPT)` (agent.py:129).
    good, confident = _run(build_agent, HOTEL_LEEDS), _run(build_confident_agent, HOTEL_LEEDS)

    assert good == ([HOTEL_LEEDS], _cited("TRV-4.2"))
    assert confident == ([], PRIOR_BELIEFS["hotel"])
    assert _run(build_confident_agent, "Can I expense a cab from the airport?")[1] == _cited("TRV-5.1")


def test_importing_the_agent_does_not_import_langchain_aws():
    # A subprocess, so no earlier import in this process can hide the result.
    # Witness s41 live import at module level: `from langchain_core.tools import tool\n` ->
    # `from langchain_core.tools import tool\nimport langchain_aws\n` (agent.py:16).
    code = "import sys, examples.policy_rag.agent; print('langchain_aws' in sys.modules)"
    completed = subprocess.run([sys.executable, "-c", code], cwd=REPO, capture_output=True, text=True)

    assert (completed.returncode, completed.stdout.strip()) == (0, "False"), completed.stderr


def test_live_agent_runs_the_good_prompt_on_bedrock_with_only_the_model_id(monkeypatch):
    # The Bedrock model is replaced by the double, so the graph runs offline with the prompt build_live_agent chose.
    # Claude Haiku 5.5 on Bedrock rejects `temperature`, so the factory must pass the model id and nothing else.
    # Witness s44 policy_rag live temperature: `ChatBedrockConverse(model=LIVE_MODEL_ID)` ->
    # `ChatBedrockConverse(model=LIVE_MODEL_ID, temperature=0)` (agent.py:136).
    # Witness s41 live agent confident prompt: `LIVE_MODEL_ID), PROMPT)` -> `LIVE_MODEL_ID), PROMPT_CONFIDENT)`
    # (agent.py:136).
    received = {}

    class FakeBedrock(SimulatedPolicyModel):
        def __init__(self, **kwargs):
            super().__init__()
            received.update(kwargs)

    fake_module = types.ModuleType("langchain_aws")
    fake_module.ChatBedrockConverse = FakeBedrock
    monkeypatch.setitem(sys.modules, "langchain_aws", fake_module)

    queries, reply = _run(build_live_agent, HOTEL_LEEDS)

    assert received == {"model": LIVE_MODEL_ID}
    assert (queries, reply) == ([HOTEL_LEEDS], _cited("TRV-4.2"))


# golden


def test_golden_has_six_dataset_cases_five_labelled_pass_and_each_reference_is_the_good_agent_reply():
    # Witness s41 golden alcohol unlabelled: `"label": "pass", "notes": "Quoted from EXP-3.4."` ->
    # `"notes": "Quoted from EXP-3.4."` (golden.jsonl:5). Witness s41 golden meal per diem figure: `USD 95 per day for
    # international travel.` -> `USD 90 per day for international travel.` (rules.py:62).
    questions = {case["id"]: case["input"] for case in _jsonl(DATASET)}
    golden = _jsonl(GOLDEN)
    replies = {entry["id"]: _run(build_agent, questions[entry["id"]])[1] for entry in golden}

    assert len(golden) == 6
    assert [entry.get("label") for entry in golden].count("pass") == 5
    assert {entry["id"]: entry["reference"] for entry in golden} == replies


# end to end, through `aea run`


@pytest.mark.slow
@pytest.mark.parametrize(
    ("factory", "failing"),
    [("build_agent", set()), ("build_confident_agent", {"hotel_cap_tier1_city", "hotel_cap_other_city"})],
    ids=["good_prompt", "confident_prompt"],
)
def test_dataset_run_passes_with_the_good_prompt_and_fails_only_the_hotel_cases_when_confident(
    tmp_path, factory, failing
):
    # A subprocess, as in test_expense.py: the tracer provider can only be set once per process.
    # Witness s41 e2e build_agent confident: `_build(SimulatedPolicyModel(), PROMPT)` ->
    # `_build(SimulatedPolicyModel(), PROMPT_CONFIDENT)` (agent.py:124).
    command = [sys.executable, "-m", "agent_accelerator.cli", "run", str(DATASET), "--adapter", "langgraph"]
    command += ["--agent", f"examples.policy_rag.agent:{factory}", "--runs-dir", str(tmp_path)]
    env = {**os.environ, "PYTHONUTF8": "1"}
    completed = subprocess.run(command, cwd=REPO, env=env, capture_output=True, text=True, encoding="utf-8")
    assert completed.returncode == 0, completed.stderr

    (run_dir,) = tmp_path.iterdir()
    results = load_results(run_dir)

    assert len(results.cases) == 11
    assert {case_id for case_id, case in results.cases.items() if not case.passed} == failing
