import numpy as np
import pytest

from src.analytics.schemas import Filters
from src.rag.chunking import chunk_text
from src.rag.embeddings import LocalEmbeddings
from src.rag.retriever import retrieve
from src.rag.service import answer_question, verify_claims


def test_sentence_chunks_preserve_text_and_boundaries():
    text = "One short sentence. Another short sentence. A third sentence. Final sentence."
    chunks = chunk_text(text, size=7, overlap=3)
    assert all(len(c.split()) <= 7 for c in chunks)
    assert all(sentence in " ".join(chunks).replace("\n", " ") for sentence in text.split(". "))
    assert chunk_text("") == []
    with pytest.raises(ValueError):
        chunk_text(text, 5, 5)


def test_long_sentence_fallback_is_bounded():
    text = " ".join(f"word{i}" for i in range(40))
    chunks = chunk_text(text, 10, 2)
    assert all(len(c.split()) <= 10 for c in chunks)
    assert set(text.split()) <= set(" ".join(chunks).split())


def test_local_embeddings_are_fitted_reproducible_vectors(sample_jobs):
    docs = [j["cleaned_description"] for j in sample_jobs]
    provider = LocalEmbeddings().fit(docs)
    values = provider.embed_documents(docs)
    assert np.asarray(values).shape == (4, 128)
    assert np.allclose(np.linalg.norm(values, axis=1), 1)
    query = provider.embed_text("Python Kubernetes pipelines")
    assert np.linalg.norm(query) > 0
    assert values[0] != values[1]


def test_retrieval_filters_and_source_traceability(indexed):
    hits, state = retrieve(
        "Python Kubernetes pipelines", Filters(country="France", job_title="Data Engineer"), indexed
    )
    assert hits and all(h["job_id"] == "1" for h in hits)
    assert hits[0]["source_url"] == "https://example.org/test/0"
    assert state["jobs"] == 4
    empty, _ = retrieve("Python", Filters(country="Atlantis"), indexed)
    assert empty == []


def test_grounded_answer_and_insufficient_evidence(indexed):
    result = answer_question(
        "Describe Kubernetes deployments", Filters(skill="Kubernetes"), indexed
    )
    assert result.sources
    lookup = {h["source_id"]: h for h in result.evidence}
    for claim in result.metadata["claims"]:
        assert claim["quote"] in lookup[claim["source_id"]]["chunk_text"]
    empty = answer_question("Describe jobs on Neptune", Filters(country="Neptune"), indexed)
    assert empty.metadata["insufficient_evidence"]
    assert not empty.sources


def test_fake_citations_and_quotes_are_rejected():
    evidence = [
        {"source_id": "S1", "chunk_text": "Build reliable production pipelines with Python."}
    ]
    assert (
        verify_claims(
            [{"text": "Claim", "source_id": "S99", "quote": evidence[0]["chunk_text"]}], evidence
        )
        == []
    )
    assert (
        verify_claims(
            [{"text": "Claim", "source_id": "S1", "quote": "This invented quote does not exist."}],
            evidence,
        )
        == []
    )


def test_llm_failure_falls_back_to_evidence(indexed, monkeypatch):
    from src.config.settings import get_settings
    from src.rag import service

    settings = get_settings().model_copy(update={"llm_provider": "openai"})
    monkeypatch.setattr(service, "get_settings", lambda: settings)

    def fail():
        raise RuntimeError("Provider down")

    monkeypatch.setattr(service, "get_client", fail)
    result = service.answer_question("Describe Kubernetes deployments", Filters(), indexed)
    assert result.metadata["mode"] == "extractive_fallback"
    assert result.sources
