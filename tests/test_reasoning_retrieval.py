import pytest
import math
from llm_kosh.engine.reasoning.causal_retrieval import resonance_profile, harmonic_match, _dct


def test_dct_length():
    x = [1.0, 2.0, 3.0, 4.0]
    result = _dct(x)
    assert len(result) == 4


def test_dct_dc_component():
    # DC component (k=0) should be 2 * sum(x)
    x = [1.0, 1.0, 1.0, 1.0]
    result = _dct(x)
    assert abs(result[0] - 2 * sum(x)) < 1e-6


def test_resonance_profile_structure():
    profile = resonance_profile("apple orange fruit healthy eating")
    assert "low" in profile
    assert "mid" in profile
    assert "high" in profile
    assert isinstance(profile["low"], list)
    assert len(profile["low"]) > 0


def test_resonance_profile_empty_text():
    profile = resonance_profile("")
    assert "low" in profile
    # Should not raise, should return zero-filled profile


def test_harmonic_match_identical():
    profile = resonance_profile("machine learning neural networks")
    score = harmonic_match(profile, profile)
    assert score > 0.9, f"Identical profiles should score near 1.0, got {score}"


def test_harmonic_match_different():
    p1 = resonance_profile("quantum physics particles")
    p2 = resonance_profile("baking bread flour yeast")
    score = harmonic_match(p1, p2)
    assert score < 0.5, f"Unrelated profiles should score low, got {score}"


def test_harmonic_match_partial():
    p1 = resonance_profile("machine learning neural networks deep")
    p2 = resonance_profile("machine learning algorithms")
    score = harmonic_match(p1, p2)
    assert 0.2 < score < 1.0, f"Partial overlap should score between 0.2 and 1.0, got {score}"
