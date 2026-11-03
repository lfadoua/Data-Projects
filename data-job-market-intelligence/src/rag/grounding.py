"""Bounded citation checks, verbatim extraction, and conservative generation guards.

Exact substring checks prove source traceability, not relevance or entailment.
Extraction uses lexical/intent heuristics and whole spans of the supplied chunks;
it cannot recover missing context outside those chunks. Natural claims are allowed
only as complete cited sentences with neutral wrappers or a bounded initial-verb
inflection. This deliberately rejects many valid paraphrases. These checks are
not a general semantic-entailment model or proof of real-world truth.
"""

import re
from collections.abc import Mapping

from src.preprocessing.skill_extractor import extract_skills, taxonomy

_STOP = set(
    "what which how why when where who are the a an of for to in and or do does is "
    "jobs job postings posting role roles expected from with about say describe "
    "tell me please can could should would need needs know senior junior lead "
    "data engineer engineers analyst analysts scientist scientists their these "
    "this that be as on at by it its they them appear appears most commonly "
    "responsibilities responsibility duties tasks skills skill technologies "
    "technology tools tool requirements requirement qualifications qualification "
    "engineering related based together alongside platforms platform services needed".split()
)
_DUTIES = re.compile(r"\b(?:responsibilit\w*|duties|tasks|work on|expected)\b", re.I)
_SKILLS = re.compile(r"\b(?:skills?|technolog\w*|tools?|qualifications?|learn|know)\b", re.I)
_ACTION_FORMS = {
    "analyze": "analyzing",
    "automate": "automating",
    "build": "building",
    "collaborate": "collaborating",
    "create": "creating",
    "deliver": "delivering",
    "deploy": "deploying",
    "design": "designing",
    "develop": "developing",
    "document": "documenting",
    "evaluate": "evaluating",
    "implement": "implementing",
    "integrate": "integrating",
    "lead": "leading",
    "maintain": "maintaining",
    "manage": "managing",
    "mentor": "mentoring",
    "monitor": "monitoring",
    "operate": "operating",
    "optimize": "optimizing",
    "prepare": "preparing",
    "research": "researching",
    "support": "supporting",
    "test": "testing",
    "train": "training",
}
_ACTIONS = re.compile(
    r"\b(?:"
    + "|".join(re.escape(form) for pair in _ACTION_FORMS.items() for form in pair)
    + r")(?:s|ed)?\b",
    re.I,
)
_BENEFITS = re.compile(
    r"\b(?:we offer|benefits package|equal opportunity|apply now|build your career|"
    r"paid vacation|health insurance)\b",
    re.I,
)
_EXTRA_TECH = re.compile(
    r"(?<!\w)(?:Rust|Java|Scala|Go|R|C\+\+|C\#|JavaScript|TypeScript|Linux|MySQL|"
    r"Redis|Elasticsearch|ClickHouse|Oracle|MATLAB|SAS|Julia|Bash)(?!\w)",
    re.I,
)
_ABBREVIATIONS = {
    "mr",
    "mrs",
    "ms",
    "dr",
    "prof",
    "sr",
    "jr",
    "e.g",
    "i.e",
    "vs",
    "u.s",
    "u.k",
    "inc",
    "ltd",
}
_WRAPPER = re.compile(
    r"^(?:(?:the|this|the cited|the retrieved|the selected|one selected|one retrieved) posting "
    r"(?:states(?: that)?|says(?: that)?|describes|mentions)\b\s*:?\s*)",
    re.I,
)
_SCOPE = set(
    "all every everyone always never most universally typically generally commonly "
    "usually often market industry worldwide nationwide".split()
)
_MODALS = set(
    "may might could can should must shall will required mandatory optional preferred "
    "essential".split()
)
_NEGATION = re.compile(r"\b(?:no|not|never|without|neither|nor|cannot)\b|\w+n['’]t\b", re.I)


def _lookup(evidence):
    result, ambiguous = {}, set()
    for source in evidence:
        if not isinstance(source, Mapping):
            continue
        source_id, text = source.get("source_id"), source.get("chunk_text")
        if not isinstance(source_id, str) or not source_id or not isinstance(text, str):
            continue
        if source_id in result and result[source_id]["chunk_text"] != text:
            ambiguous.add(source_id)
        result[source_id] = source
    return {key: value for key, value in result.items() if key not in ambiguous}


def _as_claim(value):
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    if not isinstance(value, Mapping):
        return None
    fields = ("text", "source_id", "quote")
    if any(not isinstance(value.get(field), str) for field in fields):
        return None
    return {
        "text": value["text"].strip(),
        "source_id": value["source_id"],
        "quote": value["quote"].strip(),
    }


def _exact_reason(item, sources):
    if not item or not item["text"] or not item["source_id"]:
        return "invalid_claim"
    if item["source_id"] not in sources:
        return "unknown_source"
    if len(item["quote"]) < 20:
        return "quote_too_short"
    if item["quote"] not in sources[item["source_id"]]["chunk_text"]:
        return "quote_not_exact"
    return None


def verify_exact_claims(claims, evidence):
    """Return canonical string claims with known IDs and exact quotes >=20 chars.

    Quotes are trimmed before both membership testing and return. Duplicate
    source/quote pairs and ambiguous duplicate source IDs are excluded. This
    checks traceability only; it does not validate the meaning of ``text``.
    """
    sources, accepted, seen = _lookup(evidence), [], set()
    for value in claims:
        item = _as_claim(value)
        if _exact_reason(item, sources):
            continue
        key = (item["source_id"], item["quote"])
        if key not in seen:
            accepted.append(item)
            seen.add(key)
    return accepted


def _span_offsets(text):
    """Yield whole nonblank line/sentence offsets, without rebuilding the text."""
    start = 0
    for boundary in re.finditer(r"[.!?](?=\s|$)|\n", text):
        end = boundary.end()
        if boundary.group() == ".":
            previous = text[start : end - 1].rsplit(None, 1)[-1:]
            if previous and previous[0].lower() in _ABBREVIATIONS:
                continue
        raw = text[start:end]
        if raw.strip():
            yield start + len(raw) - len(raw.lstrip()), end - len(raw) + len(raw.rstrip())
        start = end
    tail = text[start:]
    if tail.strip():
        yield start + len(tail) - len(tail.lstrip()), len(text.rstrip())


def _spans(text):
    """Yield complete nonblank lines/sentences as exact original substrings."""
    return (text[start:end] for start, end in _span_offsets(text))


def complete_quote_claims(claims, evidence):
    """Expand verified quotes to their unique original complete sentence spans.

    The result always has ``text == quote``. Midword matches are excluded and a
    quote appearing in different sentence contexts is considered ambiguous.
    Original punctuation, actors, negation and modality are preserved. A span
    means a sentence/line within the supplied chunk, not reconstructed context
    outside that chunk. Expansion alone does not establish question relevance.
    """
    sources, accepted, seen = _lookup(evidence), [], set()
    for item in verify_exact_claims(claims, evidence):
        text = sources[item["source_id"]]["chunk_text"]
        offsets, expansions = list(_span_offsets(text)), set()
        for match in re.finditer(re.escape(item["quote"]), text):
            begin, end = match.span()
            if (
                begin
                and (text[begin - 1].isalnum() or text[begin - 1] == "_")
                and item["quote"][0].isalnum()
            ) or (
                end < len(text)
                and (text[end].isalnum() or text[end] == "_")
                and item["quote"][-1].isalnum()
            ):
                continue
            first = next((left for left, right in offsets if left <= begin < right), None)
            last = next((right for left, right in offsets if left < end <= right), None)
            if first is not None and last is not None:
                expansions.add(text[first:last])
        if len(expansions) != 1:
            continue
        quote = expansions.pop()
        key = (item["source_id"], quote)
        if key not in seen:
            accepted.append({"text": quote, "source_id": item["source_id"], "quote": quote})
            seen.add(key)
    return accepted


def _tokens(value):
    return re.findall(r"[a-z0-9]+(?:[-+#.][a-z0-9]+)*", value.casefold())


def _technologies(text):
    return {name.casefold() for name in extract_skills(text)} | {
        match.group().casefold() for match in _EXTRA_TECH.finditer(text)
    }


def _topics(question):
    # Remove recognized aliases, since canonical technology anchors are checked
    # separately (e.g. k8s in the question can match Kubernetes in the quote).
    text = _EXTRA_TECH.sub(" ", question)
    for name in extract_skills(question):
        for alias in taxonomy()[name]:
            text = re.sub(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", " ", text, flags=re.I)
    return set(_tokens(text)) - _STOP


def _relevance(question, quote):
    anchors = _technologies(question)
    present = _technologies(quote)
    if not anchors <= present:
        return 0
    query = _topics(question)
    quote_terms = set(_tokens(quote))
    if present & {"aws", "azure", "gcp", "bigquery", "redshift", "sagemaker"}:
        quote_terms.add("cloud")
    overlap = len(query & quote_terms)
    if query and overlap / len(query) < 0.5:
        return 0
    if _DUTIES.search(question):
        if not _ACTIONS.search(quote) or _BENEFITS.search(quote):
            return 0
        return 2 + overlap + len(anchors)
    if anchors:
        return 2 + overlap + len(anchors)
    if _SKILLS.search(question):
        return 1 + overlap if present else 0
    if query and overlap / len(query) >= 0.5:
        return overlap
    return 0


def extract_quotes(question, evidence, limit=2, *, prefer_compact=False):
    """Select at most two relevant whole spans, with ``text == quote``.

    All named, recognized question technologies must occur in each selected
    span. Generic duties require an action cue, not an arbitrary first sentence.
    One span is selected per source/job; no model, truncation or paraphrase is
    used. Lexical relevance can miss valid evidence, so uncertain cases abstain.
    """
    if not isinstance(question, str) or not isinstance(limit, int) or limit <= 0:
        return []
    candidates = []
    for order, source in enumerate(_lookup(evidence).values()):
        scored = [
            (_relevance(question, quote), index, quote)
            for index, quote in enumerate(_spans(source["chunk_text"]))
            if len(quote) >= 20
        ]
        if not scored:
            continue
        score, _, quote = max(
            scored,
            key=lambda value: (
                value[0],
                -len(value[2]) if prefer_compact else -value[1],
                -value[1],
            ),
        )
        if score:
            candidates.append((-score, order, source, quote))
    accepted, jobs, quotes = [], set(), set()
    for _, _, source, quote in sorted(candidates, key=lambda value: value[:2]):
        job = source.get("job_id") or source["source_id"]
        if job in jobs or quote in quotes:
            continue
        accepted.append({"text": quote, "source_id": source["source_id"], "quote": quote})
        jobs.add(job)
        quotes.add(quote)
        if len(accepted) >= min(limit, 2):
            break
    return accepted


def _normalized(value):
    return " ".join(value.split()).casefold()


def _body(text):
    body = _WRAPPER.sub("", text, count=1).strip()
    if len(body) >= 2 and (body[0], body[-1]) in {('"', '"'), ("“", "”"), ("'", "'")}:
        body = body[1:-1].strip()
    return body


def _supported_form(body, quote):
    body, quote = (_normalized(re.sub(r"^[-*•]\s+", "", value)) for value in (body, quote))
    # A final full stop on an unpunctuated source line changes presentation only.
    # Never strip source punctuation, question/exclamation marks or interior commas.
    if quote and quote[-1] not in ".!?" and body.endswith("."):
        body = body[:-1]
    if body == quote:
        return True
    first, separator, rest = quote.partition(" ")
    if separator and first in _ACTION_FORMS:
        return body == _ACTION_FORMS[first] + " " + rest
    return False


def _scope_role_statement(item, source):
    """Narrow a title-matched role sentence to one posting and an unchanged duty.

    Only a complete imperative quote (or its initial gerund) can be retained.
    The role prefix is never used to justify new predicates or population claims.
    """
    match = re.fullmatch(
        r"(?:The )?([A-Za-z][A-Za-z .-]{1,75}?) (?:are|is) "
        r"(?:expected to|responsible for) (.+)",
        item["text"],
        re.I,
    )
    if not match:
        return item
    role, predicate = match.groups()
    role_tokens = {t[:-1] if t.endswith("s") else t for t in _tokens(role)} - {"the"}
    title_tokens = {t[:-1] if t.endswith("s") else t for t in _tokens(source.get("job_title", ""))}
    if not role_tokens or not role_tokens <= title_tokens:
        return item
    first, separator, rest = item["quote"].partition(" ")
    if not separator or first.casefold() not in _ACTION_FORMS:
        return item
    if not _supported_form(predicate, item["quote"]):
        return item
    text = "This posting describes " + _ACTION_FORMS[first.casefold()] + " " + rest
    return {**item, "text": text}


def _natural_reason(item, source, question):
    quote, body = item["quote"], _body(item["text"])
    if not any(quote == span for span in _spans(source["chunk_text"])):
        return "quote_not_complete_span"
    if not _relevance(question, quote):
        return "irrelevant_quote"
    claim_tokens, quote_tokens = set(_tokens(body)), set(_tokens(quote))
    if _technologies(body) - _technologies(quote):
        return "unsupported_technology"
    if re.findall(r"\d+(?:[.,]\d+)*%?", body) != re.findall(r"\d+(?:[.,]\d+)*%?", quote):
        return "number_changed"
    if (claim_tokens & _SCOPE) - (quote_tokens & _SCOPE):
        return "scope_strengthened"
    if set(_NEGATION.findall(body.casefold())) != set(_NEGATION.findall(quote.casefold())):
        return "negation_changed"
    if (claim_tokens & _MODALS) != (quote_tokens & _MODALS):
        return "modality_changed"
    if _supported_form(body, quote):
        return None
    # Capitalized names are a conservative diagnostic, not named-entity recognition.
    names = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", body)
    if any(name.casefold() not in quote.casefold() for name in names):
        return "unsupported_entity"
    known_inflections = set(_ACTION_FORMS.values())
    if claim_tokens - quote_tokens - known_inflections:
        return "unsupported_content"
    return "unsupported_rephrasing_or_actor_relation"


def natural_supported_claims(claims, evidence, question):
    """Return ``(accepted, rejections)`` using a deliberately closed guard.

    Accepted natural wording is limited to a complete cited span, a neutral
    posting-attribution wrapper, or its initial imperative verb in gerund form.
    Numbers, technology anchors, scope, negation and modality are checked first.
    Bag-of-words overlap cannot authorize actor/relation changes. Rejections
    contain indices/IDs/reasons only, not full source documents. This is a
    bounded lexical/syntactic policy, NOT a semantic-entailment proof; callers
    should use exact quote fallback rather than relaxing uncertain cases.
    """
    sources, accepted, rejected, seen = _lookup(evidence), [], [], set()
    for index, value in enumerate(claims):
        item = _as_claim(value)
        reason = _exact_reason(item, sources)
        if not reason:
            item = _scope_role_statement(item, sources[item["source_id"]])
            reason = _natural_reason(item, sources[item["source_id"]], question)
        if reason:
            rejected.append(
                {"index": index, "source_id": item["source_id"] if item else None, "reason": reason}
            )
            continue
        key = (item["source_id"], item["quote"])
        if key not in seen:
            accepted.append(item)
            seen.add(key)
    return accepted, rejected
