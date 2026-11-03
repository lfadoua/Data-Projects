"""Pure grounding regressions; no database, model, network or settings reads."""

import pytest

from src.rag.grounding import (
    complete_quote_claims,
    extract_quotes,
    natural_supported_claims,
    verify_exact_claims,
)


def source(text, source_id="S1", job_id="job-1"):
    return {"source_id": source_id, "job_id": job_id, "chunk_text": text}


def claim(text, quote, source_id="S1"):
    return {"text": text, "source_id": source_id, "quote": quote}


def test_title_matched_role_prefix_is_narrowed_to_the_posting_only():
    quote = "Build Python data pipelines with SQL and Airflow."
    evidence = [{**source(quote), "job_title": "Senior Data Engineer"}]
    accepted, rejected = natural_supported_claims(
        [
            claim(
                "Data Engineers are expected to build Python data pipelines with SQL and Airflow.",
                quote,
            )
        ],
        evidence,
        "What responsibilities are expected from Data Engineers?",
    )
    assert not rejected
    assert accepted == [
        claim("This posting describes building Python data pipelines with SQL and Airflow.", quote)
    ]


def test_compact_context_prefers_shorter_equally_relevant_complete_evidence():
    long = "Build reliable and well documented Python data pipelines for production systems."
    short = "Monitor data quality in production."
    values = [source(long + " " + short)]
    question = "What responsibilities are expected from Data Engineers?"
    assert extract_quotes(question, values)[0]["quote"] == long
    assert extract_quotes(question, values, prefer_compact=True)[0]["quote"] == short


@pytest.mark.parametrize(
    "text,title",
    [
        (
            "Data Engineers are expected to build Python data pipelines with SQL and Airflow.",
            "Data Analyst",
        ),
        (
            "All Data Engineers are expected to build Python data pipelines with SQL and Airflow.",
            "Data Engineer",
        ),
        (
            "Data Engineers are expected to build Python data pipelines "
            "and manage business projects.",
            "Data Engineer",
        ),
        (
            "Data Engineers are expected to not build Python data pipelines with SQL and Airflow.",
            "Data Engineer",
        ),
    ],
)
def test_role_scoping_cannot_add_predicates_negation_or_market_scope(text, title):
    quote = "Build Python data pipelines with SQL and Airflow."
    accepted, rejected = natural_supported_claims(
        [claim(text, quote)],
        [{**source(quote), "job_title": title}],
        "What responsibilities are expected from Data Engineers?",
    )
    assert not accepted and rejected


def test_exact_normalizes_returned_quote_and_deduplicates_without_paraphrase_validation():
    quote = "Build reliable production pipelines with Python."
    values = [claim("  Unverified paraphrase  ", f"\n {quote} \t")] * 2
    accepted = verify_exact_claims(values, [source(quote)])
    assert accepted == [claim("Unverified paraphrase", quote)]
    assert accepted[0]["quote"] in quote


@pytest.mark.parametrize(
    "value",
    [
        claim("Build pipelines", "Build reliable production pipelines with Python.", "S99"),
        claim("Build pipelines", "Build reliable production pipelines with Python.", " S1 "),
        claim("Build pipelines", "This quotation was completely invented."),
        claim("Build pipelines", "Python"),
        {"text": 4, "source_id": "S1", "quote": "Build reliable production pipelines."},
        {"text": "Claim", "source_id": "S1"},
        claim("", "Build reliable production pipelines with Python."),
        None,
    ],
)
def test_exact_rejects_unknown_fake_short_malformed_and_nonstring_values(value):
    assert not verify_exact_claims(
        [value], [source("Build reliable production pipelines with Python.")]
    )


def test_ambiguous_duplicate_source_ids_cannot_establish_traceability():
    quote = "Build reliable production pipelines with Python."
    evidence = [source(quote), source("Analyze financial information with SQL.")]
    assert not verify_exact_claims([claim(quote, quote)], evidence)
    assert not extract_quotes("What Python skills are needed?", evidence)


def test_complete_quotes_expand_partial_claims_to_preserve_negation_actor_and_modality():
    full = "Managers may not require SQL experience for this position."
    fragment = "require SQL experience for this position."
    expanded = complete_quote_claims(
        [claim("SQL experience is required.", fragment)], [source(full)]
    )
    assert expanded == [claim(full, full)]
    assert expanded[0]["quote"] in full


def test_complete_quotes_reject_ambiguous_contexts_midword_and_unknown_source():
    fragment = "SQL experience is required for this position."
    ambiguous = "No " + fragment + " " + fragment
    assert not complete_quote_claims([claim(fragment, fragment)], [source(ambiguous)])
    midword = "aintain reliable production SQL pipelines."
    assert not complete_quote_claims([claim(midword, midword)], [source("M" + midword)])
    assert not complete_quote_claims([claim(fragment, fragment, "S9")], [source(fragment)])


def test_complete_quotes_preserve_multisentence_spans_and_deduplicate_expansions():
    first = "Build reliable SQL pipelines for production."
    second = "You must not manage business projects."
    full = first + "\n" + second
    fragment = "SQL pipelines for production.\nYou must not manage"
    values = [claim(fragment, fragment), claim(full, full)]
    assert complete_quote_claims(values, [source(full)]) == [claim(full, full)]


def test_extract_preserves_whole_sentence_case_punctuation_and_negation():
    quote = "You will NOT manage projects, and you must maintain SQL data pipelines."
    evidence = [source("We offer a generous benefits package. " + quote + " Apply now!")]
    accepted = extract_quotes("What responsibilities are expected from Data Engineers?", evidence)
    assert accepted == [claim(quote, quote)]
    assert accepted[0]["quote"] in evidence[0]["chunk_text"]


def test_extract_does_not_truncate_a_long_sentence_or_infer_a_task_from_a_summary():
    quote = (
        "Build reliable data pipelines using Python and SQL for internal analytics teams, "
        "carefully maintaining monitoring, deployment, testing and documentation across "
        "multiple source systems and regional environments."
    )
    assert len(quote.split()) > 20
    evidence = [source("Our organization has a long and successful history.\n" + quote)]
    assert extract_quotes("Describe Data Engineer responsibilities", evidence) == [
        claim(quote, quote)
    ]
    assert not extract_quotes(
        "Describe Data Engineer responsibilities",
        [source("Our organization has a long and successful history with many customers.")],
    )


def test_extract_requires_all_question_technology_anchors_in_the_selected_sentence():
    evidence = [source("Build data pipelines using Python. Maintain reliable SQL data services.")]
    assert not extract_quotes("What Python and SQL responsibilities are expected?", evidence)
    assert not extract_quotes("What Kubernetes skills are expected?", evidence)
    assert not extract_quotes("What Rust skills are expected?", evidence)
    both = "Build reliable data pipelines using Python and SQL."
    assert extract_quotes("What Python and SQL skills are needed?", [source(both)]) == [
        claim(both, both)
    ]


def test_extract_prioritizes_relevance_then_distinct_jobs_and_sources_with_two_claim_cap():
    a = "Build reliable Python data pipelines and SQL warehouses."
    b = "Deploy scalable Python services to production platforms."
    c = "Maintain reliable Python data integrations across teams."
    evidence = [source(a), source(b, "S2", "job-1"), source(c, "S3", "job-2")]
    accepted = extract_quotes("What Python responsibilities are expected?", evidence, limit=20)
    assert len(accepted) == 2
    lookup = {item["source_id"]: item for item in evidence}
    assert len({lookup[item["source_id"]]["job_id"] for item in accepted}) == 2
    assert all(item["text"] == item["quote"] for item in accepted)
    assert all(item["quote"] in lookup[item["source_id"]]["chunk_text"] for item in accepted)
    assert len(extract_quotes("What Python responsibilities are expected?", evidence, 1)) == 1
    assert not extract_quotes("What Python responsibilities are expected?", evidence, 0)


def test_extract_keeps_bullet_span_and_does_not_split_abbreviations():
    quote = "- Collaborate with Sr. Engineers to maintain SQL production pipelines."
    evidence = [source("Responsibilities:\n" + quote)]
    assert extract_quotes("What SQL responsibilities appear?", evidence) == [claim(quote, quote)]


def test_extract_abstains_when_an_unrecognized_subject_is_irrelevant():
    evidence = [source("Build reliable data pipelines using Python and SQL.")]
    assert not extract_quotes("Describe quantum teleportation research", evidence)
    assert not extract_quotes("What responsibilities are expected from doctors?", evidence)
    assert not extract_quotes("What Python project management responsibilities appear?", evidence)


def test_extract_handles_technology_aliases_and_cloud_topic_without_unrelated_skills():
    quote = "Maintain reliable Kubernetes deployment pipelines."
    assert extract_quotes("What k8s responsibilities are expected?", [source(quote)]) == [
        claim(quote, quote)
    ]
    cloud = "Build production data pipelines using AWS services."
    assert extract_quotes("What cloud platforms and skills are needed?", [source(cloud)]) == [
        claim(cloud, cloud)
    ]
    assert not extract_quotes(
        "What cloud platforms and skills are needed?",
        [source("Build production data pipelines using SQL.")],
    )


@pytest.mark.parametrize(
    ("quote", "text"),
    [
        (
            "Engineers maintain reliable Python data pipelines.",
            "The cited posting states that engineers maintain reliable Python data pipelines.",
        ),
        (
            "Build reliable Python data pipelines.",
            "One selected posting describes building reliable Python data pipelines.",
        ),
        ("Build reliable Python data pipelines.", "Building reliable Python data pipelines."),
        (
            "You will not manage projects and must maintain SQL pipelines.",
            "The posting states: You will not manage projects and must maintain SQL pipelines.",
        ),
    ],
)
def test_natural_allows_bounded_whole_clause_attribution_and_initial_verb_inflection(quote, text):
    accepted, rejected = natural_supported_claims(
        [claim(text, quote)], [source(quote)], "Describe Data Engineer responsibilities"
    )
    assert accepted == [claim(text, quote)]
    assert not rejected


@pytest.mark.parametrize(
    ("quote", "text", "reason"),
    [
        (
            "Develop, evaluate, test and maintain architectures and data solutions.",
            "Develop data solutions and manage business projects with industry compliance.",
            "scope_strengthened",
        ),
        (
            "Build reliable SQL pipelines for internal analytics.",
            "Build reliable SQL pipelines and ensure regulatory compliance.",
            "unsupported_content",
        ),
        (
            "Build reliable SQL pipelines for internal analytics.",
            "Build reliable SQL and Kubernetes pipelines for internal analytics.",
            "unsupported_technology",
        ),
        (
            "Manage 2 reliable SQL pipelines for internal analytics.",
            "Manage 20 reliable SQL pipelines for internal analytics.",
            "number_changed",
        ),
        (
            "Build reliable SQL pipelines for internal analytics.",
            "All engineers build reliable SQL pipelines for internal analytics.",
            "scope_strengthened",
        ),
        (
            "You must not build production SQL pipelines.",
            "You must build production SQL pipelines.",
            "negation_changed",
        ),
        (
            "You may build reliable production SQL pipelines.",
            "You must build reliable production SQL pipelines.",
            "modality_changed",
        ),
        (
            "Build reliable SQL pipelines for Acme analytics.",
            "Build reliable SQL pipelines for Globex analytics.",
            "unsupported_entity",
        ),
        (
            "Managers work with engineers who build SQL data pipelines.",
            "Managers build SQL data pipelines.",
            "unsupported_rephrasing_or_actor_relation",
        ),
    ],
)
def test_natural_rejects_unjustified_details_and_relation_changes(quote, text, reason):
    accepted, rejected = natural_supported_claims(
        [claim(text, quote)], [source(quote)], "Describe Data Engineer responsibilities"
    )
    assert not accepted
    assert rejected == [{"index": 0, "source_id": "S1", "reason": reason}]


def test_natural_rejects_a_substring_that_removes_the_original_negation():
    full = "You must not build reliable SQL production pipelines."
    fragment = "build reliable SQL production pipelines."
    assert verify_exact_claims([claim(fragment, fragment)], [source(full)])
    accepted, rejected = natural_supported_claims(
        [claim(fragment, fragment)], [source(full)], "Describe SQL responsibilities"
    )
    assert not accepted
    assert rejected[0]["reason"] == "quote_not_complete_span"


def test_natural_rejects_real_but_irrelevant_quotes_and_keeps_only_accepted_traces():
    relevant = "Maintain reliable SQL production pipelines."
    irrelevant = "Employees enjoy comprehensive health insurance and paid vacation."
    evidence = [source(relevant), source(irrelevant, "S2", "job-2")]
    accepted, rejected = natural_supported_claims(
        [claim(relevant, relevant), claim(irrelevant, irrelevant, "S2")],
        evidence,
        "Describe SQL responsibilities",
    )
    assert accepted == [claim(relevant, relevant)]
    assert rejected == [{"index": 1, "source_id": "S2", "reason": "irrelevant_quote"}]
    assert {item["source_id"] for item in accepted} == {"S1"}


def test_natural_reports_unknown_sources_and_invented_quotes_without_full_source_text():
    quote = "Maintain reliable SQL production pipelines."
    accepted, rejected = natural_supported_claims(
        [claim(quote, quote, "S99"), claim(quote, "An invented supporting quote for SQL.")],
        [source(quote)],
        "Describe SQL responsibilities",
    )
    assert not accepted
    assert [item["reason"] for item in rejected] == ["unknown_source", "quote_not_exact"]
    assert all(set(item) == {"index", "source_id", "reason"} for item in rejected)


def test_natural_does_not_turn_a_source_question_into_an_assertion():
    quote = "Engineers build reliable SQL data pipelines?"
    text = "Engineers build reliable SQL data pipelines."
    accepted, rejected = natural_supported_claims(
        [claim(text, quote)], [source(quote)], "Describe SQL responsibilities"
    )
    assert not accepted
    assert rejected[0]["reason"] == "unsupported_rephrasing_or_actor_relation"


def test_observed_added_full_stop_keeps_original_quote_and_all_words():
    quote = "Mentors junior team members in best practices and standards"
    item = claim("This posting states: " + quote + ".", quote)
    accepted, rejected = natural_supported_claims(
        [item], [source(quote)], "What responsibilities are expected from Senior Data Engineers?"
    )
    assert accepted == [item]
    assert accepted[0]["quote"] == quote
    assert not rejected


@pytest.mark.parametrize(
    "text",
    [
        "Mentors all junior team members in best practices and standards.",
        "Mentors junior team members in best practices and industry standards.",
        "Mentors junior team members in best practices and standards?",
        "Mentors junior team members in best practices and standards!",
    ],
)
def test_terminal_presentation_equivalence_does_not_allow_content_or_force_changes(text):
    quote = "Mentors junior team members in best practices and standards"
    accepted, rejected = natural_supported_claims(
        [claim("This posting states: " + text, quote)],
        [source(quote)],
        "Describe Senior Data Engineer responsibilities",
    )
    assert not accepted and rejected
