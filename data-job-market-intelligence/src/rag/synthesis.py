"""Conservative, non-generative synthesis of literal posting evidence.

Every statement refers to an exact sentence inside a selected posting. Counts
describe selected evidence only, never the full corpus or a hiring trend.
"""

import re
from collections import Counter, defaultdict

from src.preprocessing.skill_extractor import extract_skills

THEMES = [
    ("Data pipelines or ingestion", r"\b(?:pipeline|etl|ingest|data flow)\w*\b"),
    ("SQL, data modeling, or warehousing", r"\b(?:data model|sql|warehouse|database)\w*\b"),
    (
        "Cloud infrastructure or deployment",
        r"\b(?:aws|azure|gcp|cloud|deploy|kubernetes|docker)\w*\b",
    ),
    (
        "Reliability, monitoring, or quality",
        r"\b(?:monitor|quality|reliab|test|optim|performan)\w*\b",
    ),
    ("Team or stakeholder collaboration", r"\b(?:collaborat|stakeholder|partner with)\w*\b"),
]
CLOUD = {"AWS", "Azure", "GCP", "BigQuery", "Redshift", "SageMaker", "Snowflake", "Databricks"}


def sentences(text):
    return [
        part.strip(" \t-•")
        for part in re.split(r"(?<=[.!?])\s+|\n+", text)
        if len(part.strip()) >= 25
    ]


def first_quote(source, pattern=None, skill=None):
    for sentence in sentences(source["chunk_text"]):
        if (pattern and re.search(pattern, sentence, re.I)) or (
            skill and skill in extract_skills(sentence)
        ):
            return sentence
    return None


def anchored_quote(source, anchor, pattern):
    """Require the named technology and responsibility in the same sentence."""
    for sentence in sentences(source["chunk_text"]):
        if anchor in extract_skills(sentence) and re.search(pattern, sentence, re.I):
            return sentence
    return None


def claim(text, source, quote):
    return {"text": text, "source_id": source["source_id"], "quote": quote}


def synthesize(question, evidence):
    """Return answer, points, and checkable claims from distinct selected jobs."""
    if not evidence:
        return (
            "The retrieved postings do not provide enough evidence to answer this reliably.",
            [],
            [],
        )
    lower = question.lower()
    skills = defaultdict(list)
    for source in evidence:
        for name in extract_skills(source["chunk_text"]):
            quote = first_quote(source, skill=name)
            if quote:
                skills[name].append((source, quote))
    requested = extract_skills(question)
    cooccurrence = bool(re.search(r"\b(?:together|alongside|with|co-occur)\b", lower))
    cloud_only = "cloud" in lower
    if cooccurrence and requested:
        anchor = requested[0]
        evidence = [s for s in evidence if anchor in extract_skills(s["chunk_text"])]
        skills = defaultdict(list)
        for source in evidence:
            for name in extract_skills(source["chunk_text"]):
                if name != anchor:
                    quote = first_quote(source, skill=name)
                    if quote:
                        skills[name].append((source, quote))
        intro = (
            f"In the retrieved postings that mention {anchor}, these other tracked "
            "technologies appear:"
        )
    elif cloud_only:
        skills = {name: refs for name, refs in skills.items() if name in CLOUD}
        intro = "The retrieved Data Engineer examples mention these cloud platforms and services:"
    elif re.search(r"\b(?:learn|prepare)\b", lower):
        intro = "To prepare for this role, the retrieved postings point to these skills:"
    else:
        intro = "Across the retrieved postings, these tracked skills appear:"
    ranked = sorted(skills.items(), key=lambda item: (-len(item[1]), item[0]))
    if len(evidence) >= 3 and any(len(refs) >= 2 for _, refs in ranked):
        ranked = [(name, refs) for name, refs in ranked if len(refs) >= 2]
    claims, points = [], []
    wants_responsibilities = bool(re.search(r"\b(?:responsibilit|duties|work on)\w*\b", lower))
    if not wants_responsibilities:
        for name, refs in ranked[:5]:
            ids = ", ".join(f"[{s['source_id']}]" for s, _ in refs)
            points.append(f"{name} — present in {len(refs)} selected posting(s) {ids}")
            claims.extend(claim(name, source, quote) for source, quote in refs)
    theme_points = []
    if wants_responsibilities or "learn" in lower or "prepare" in lower:
        for title, pattern in THEMES:
            matches = []
            for source in evidence:
                quote = (
                    anchored_quote(source, requested[0], pattern)
                    if wants_responsibilities and requested
                    else first_quote(source, pattern=pattern)
                )
                if quote:
                    matches.append((source, quote))
            if len(matches) >= (1 if len(evidence) < 3 else 2):
                refs = ", ".join(f"[{s['source_id']}]" for s, _ in matches)
                theme_points.append(f"{title} {refs}")
                claims.extend(claim(title, source, quote) for source, quote in matches)
            if len(theme_points) >= 3:
                break
    if wants_responsibilities:
        points = theme_points
        intro = (
            f"In the selected postings, {requested[0]} appears in responsibilities involving:"
            if requested
            else "The selected postings describe these responsibilities:"
        )
    elif theme_points:
        points.extend(theme_points[:2])
    if not points:
        return (
            "The retrieved postings do not provide enough direct evidence to answer this reliably.",
            [],
            [],
        )
    answer = intro + "\n\n" + "\n".join(f"• {point}" for point in points)
    answer += "\n\nThese are observations from the selected postings, not market-wide frequencies."
    return answer, points, claims


def evidence_quality(evidence, claims):
    """A documented label from observable coverage; cosine is not probability."""
    if not claims:
        return "Limited evidence"
    jobs = len({s["job_id"] for s in evidence})
    links = sum(
        bool((s.get("source_url") or "").startswith(("https://", "http://"))) for s in evidence
    )
    best = max((s["similarity"] for s in evidence), default=0)
    support = Counter(claim["text"] for claim in claims)
    repeated = sum(count >= 2 for count in support.values())
    if jobs >= 4 and links >= 3 and best >= 0.55 and repeated >= 2:
        return "Strong evidence"
    if jobs >= 2 and links >= 1 and best >= 0.35 and repeated >= 1:
        return "Moderate evidence"
    return "Limited evidence"


def excerpt(source, question):
    """Short relevant display excerpt; full chunk remains in the API evidence."""
    query = set(re.findall(r"[a-z][a-z0-9+#.-]{2,}", question.lower()))
    choices = sentences(source["chunk_text"])
    if not choices:
        return source["chunk_text"][:320]
    chosen = max(
        choices,
        key=lambda item: len(query & set(re.findall(r"[a-z][a-z0-9+#.-]{2,}", item.lower()))),
    )
    return chosen[:320] + ("…" if len(chosen) > 320 else "")
