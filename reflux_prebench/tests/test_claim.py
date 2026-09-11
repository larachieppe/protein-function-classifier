"""The frozen claim must be internally consistent and affordable to test."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from prebench.claim import (FrozenClaim, clopper_pearson, n_for_lower_bound,
                            n_for_upper_bound)

CLAIM = ROOT / "claim" / "frozen_claim.yaml"


@pytest.fixture(scope="module")
def claim():
    return FrozenClaim.load(CLAIM)


def test_claim_validates(claim):
    assert claim.validate() == []


def test_hash_is_stable_and_content_addressed(claim):
    h1 = claim.content_hash
    claim.raw["claim"]["statement"] = "edited rationale text"
    assert claim.content_hash == h1, "editorial text must not move the hash"
    claim.raw["thresholds"]["detection"]["fbr_min_db"] = 7.0
    assert claim.content_hash != h1, "changing a threshold must move the hash"


def test_three_outcomes_are_exhaustive(claim):
    outcomes = claim.raw["outcomes"]
    assert set(outcomes) == {"positive", "negative", "indeterminate"}
    assert "adequate" in outcomes["negative"]["label"].lower() or \
           any("observ" in c.lower() for c in outcomes["negative"]["all_of"])


def test_negative_requires_demonstrated_observability(claim):
    """'Not seen' must never silently become 'not present'."""
    conds = " ".join(claim.raw["outcomes"]["negative"]["all_of"]).lower()
    assert "both registered positions were observed" in conds


def test_every_mechanism_has_a_stopping_rule_and_a_limit(claim):
    rules = claim.raw["stopping_rules"]
    for key in ("M1", "M2", "M3", "M4", "M5", "M6"):
        assert key in rules
        assert rules[key]["stop_when"].strip()
        assert rules[key]["does_not_close"].strip(), \
            f"{key} closure must state what it does NOT close"


def test_composite_can_never_close_alone(claim):
    assert "never" in claim.raw["stopping_rules"]["M6"]["stop_when"].lower()


def test_detection_threshold_sits_above_the_estimator_floor(claim):
    assert claim.threshold("detection", "fbr_min_db") > \
        claim.threshold("detection", "estimator_floor_db")


def test_trial_counts_are_finite_and_reported(claim):
    tc = claim.trial_counts()
    for key, v in tc.items():
        n = v.get("n_trials") or v.get("n_trials_zero_failures")
        assert n and n > 0, key
        assert n < 10000, f"{key} needs {n} trials: the threshold is unaffordable"


def test_rule_of_three_behaviour():
    assert n_for_upper_bound(0.05) == pytest.approx(72, abs=5)
    assert n_for_upper_bound(0.01) == pytest.approx(368, abs=20)


def test_clopper_pearson_matches_known_values():
    lo, hi = clopper_pearson(0, 100)
    assert lo == 0.0
    assert hi == pytest.approx(0.0362, abs=0.002)
    lo, hi = clopper_pearson(50, 100)
    assert lo == pytest.approx(0.3983, abs=0.003)
    assert hi == pytest.approx(0.6017, abs=0.003)


def test_lower_bound_sample_size():
    assert 40 <= n_for_lower_bound(0.90, 0.80) <= 80


def test_falsifiers_exist(claim):
    assert len(claim.raw["falsifiers"]) >= 3


def test_claim_is_not_frozen_until_signed_off(claim):
    assert claim.raw["frozen_on"] is None
    assert "AWAITING" in claim.raw["status"]
    assert all(v is None for k, v in claim.raw["sign_off"].items() if k != "note")
