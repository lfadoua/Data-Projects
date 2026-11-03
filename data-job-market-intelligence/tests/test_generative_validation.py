"""Do not count fallback or a model abstention as an accepted natural answer."""

from evaluation.generative_validation import generation_summary


def test_rates_exclude_warmup_no_call_cases_and_model_abstention():
    accepted = {
        "warmup": False,
        "generation_attempted": True,
        "generation_used": True,
        "mode": "ollama",
        "output_mode": "generated_synthesis",
        "claim_count": 1,
        "insufficient_evidence": False,
    }
    fallback = {**accepted, "mode": "extractive_fallback", "generation_used": False}
    abstained = {**accepted, "insufficient_evidence": True, "claim_count": 0}
    no_call = {**abstained, "generation_attempted": False, "generation_used": False}
    result = generation_summary(
        [{**accepted, "warmup": True}, accepted, fallback, abstained, no_call]
    )
    assert result["measured_cases"] == 4
    assert result["generation_attempts"] == 3
    assert result["accepted_generated_responses"] == 1
    assert result["extractive_fallbacks"] == 1
    assert result["model_abstentions"] == 1
    assert result["no_generation_cases"] == 1
    assert result["accepted_rate_of_attempts"] == 1 / 3
    assert result["fallback_rate_of_attempts"] == 1 / 3


def test_no_attempts_has_no_invented_acceptance_rate():
    result = generation_summary([{"warmup": False}])
    assert result["accepted_rate_of_attempts"] is None
    assert result["fallback_rate_of_attempts"] is None
