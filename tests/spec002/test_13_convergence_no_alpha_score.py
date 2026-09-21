"""TEST 13 -- Convergence without Alpha Score (Spec #002 SS38/SS20/SS24).

Multiple active lanes -> descriptive convergence output; no global
predictive score anywhere, in the data model or in the computed output.
"""
from discovery.candidate.convergence import active_lanes_for
from discovery.models.entities import DiscoveryCandidate, StateSignature


def test_convergence_produces_active_lanes_not_a_score():
    sig = StateSignature(
        security_id="sec_x", as_of="2026-01-01", timeframe="1D",
        lane_states={
            "trend": "HIGH", "relative_strength": "VERY_HIGH", "volatility": "COMPRESSION",
            "volume": "NEUTRAL", "momentum": "NEUTRAL",
        },
        feature_vector={}, normalized_feature_vector={}, persistence=1,
    )
    active = active_lanes_for(sig)
    assert set(active) == {"trend", "relative_strength", "volatility"}


def test_discovery_candidate_has_no_score_field():
    fields = set(DiscoveryCandidate.__dataclass_fields__.keys())
    for forbidden in ("alpha_score", "score", "win_rate", "expectancy", "sharpe"):
        assert forbidden not in fields, f"forbidden scoring field '{forbidden}' present on DiscoveryCandidate"
