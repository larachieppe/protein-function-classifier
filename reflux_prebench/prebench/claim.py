"""The frozen experimental claim: load it, validate it, hash it, and cost it.

The claim is stored as data (claim/frozen_claim.yaml) rather than as code, so that the
thresholds can be signed off and hashed before any data exists.  This module:

  * loads and validates the claim,
  * computes the content hash that identifies the frozen version,
  * converts every rate threshold into the number of trials needed to test it, and
  * checks the thresholds against each other for internal contradictions.

The sample sizes are the part that usually gets skipped.  A false-alarm ceiling of 1% is
not a threshold unless somebody runs the ~300 control acquisitions that could detect a
violation; stating the ceiling without the trial count is how an underpowered bench
declares success.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# Binomial confidence intervals without scipy
# ---------------------------------------------------------------------------

def _log_beta(a: float, b: float) -> float:
    return math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)


def _betainc(a: float, b: float, x: float) -> float:
    """Regularised incomplete beta function I_x(a, b) by continued fraction."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    if x > (a + 1.0) / (a + b + 2.0):
        return 1.0 - _betainc(b, a, 1.0 - x)
    lbeta = _log_beta(a, b)
    front = math.exp(a * math.log(x) + b * math.log(1.0 - x) - lbeta) / a
    f, c, d = 1.0, 1.0, 0.0
    for i in range(0, 300):
        m = i // 2
        if i == 0:
            num = 1.0
        elif i % 2 == 0:
            num = (m * (b - m) * x) / ((a + 2.0 * m - 1.0) * (a + 2.0 * m))
        else:
            num = -((a + m) * (a + b + m) * x) / ((a + 2.0 * m) * (a + 2.0 * m + 1.0))
        d = 1.0 + num * d
        d = 1e-30 if abs(d) < 1e-30 else d
        d = 1.0 / d
        c = 1.0 + num / c
        c = 1e-30 if abs(c) < 1e-30 else c
        f *= c * d
        if abs(1.0 - c * d) < 1e-12:
            break
    return front * (f - 1.0)


def _beta_ppf(p: float, a: float, b: float) -> float:
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if _betainc(a, b, mid) < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def clopper_pearson(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Exact two-sided (1-alpha) binomial interval for k successes in n trials."""
    lo = 0.0 if k == 0 else _beta_ppf(alpha / 2.0, k, n - k + 1)
    hi = 1.0 if k == n else _beta_ppf(1.0 - alpha / 2.0, k + 1, n - k)
    return lo, hi


def n_for_upper_bound(p_ceiling: float, observed_failures: int = 0,
                      alpha: float = 0.05) -> int:
    """Trials needed so that ``observed_failures`` still bounds the rate below p_ceiling.

    With zero observed failures this reduces to the rule of three (n ~ 3/p).
    """
    n = max(observed_failures + 1, 1)
    while n < 200000:
        _lo, hi = clopper_pearson(observed_failures, n, alpha)
        if hi <= p_ceiling:
            return n
        n += 1 if n < 400 else max(1, n // 100)
    return -1


def n_for_lower_bound(p_target: float, p_floor: float, alpha: float = 0.05) -> int:
    """Trials needed so that an observed rate p_target has a lower bound above p_floor."""
    n = 5
    while n < 100000:
        k = int(round(p_target * n))
        lo, _hi = clopper_pearson(k, n, alpha)
        if lo >= p_floor:
            return n
        n += 1 if n < 500 else max(1, n // 100)
    return -1


# ---------------------------------------------------------------------------
# The claim object
# ---------------------------------------------------------------------------

@dataclass
class FrozenClaim:
    raw: dict[str, Any]
    path: Path

    @classmethod
    def load(cls, path: str | Path) -> "FrozenClaim":
        p = Path(path)
        return cls(yaml.safe_load(p.read_text()), p)

    # -- identity ---------------------------------------------------------------
    @property
    def content_hash(self) -> str:
        """SHA-256 over the canonicalised thresholds only.

        Editorial changes to rationale text do not change the hash; changing any number
        does.  A bench result is only reportable against a hash that predates it.
        """
        payload = json.dumps(self.raw.get("thresholds", {}), sort_keys=True,
                             separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()

    @property
    def short_hash(self) -> str:
        return self.content_hash[:12]

    def threshold(self, *keys: str) -> Any:
        node: Any = self.raw["thresholds"]
        for k in keys:
            node = node[k]
        return node

    # -- validation -------------------------------------------------------------
    def validate(self) -> list[str]:
        problems: list[str] = []
        t = self.raw.get("thresholds", {})

        required = ["detection", "direction", "tracking", "accuracy", "repeatability",
                    "stopping"]
        for key in required:
            if key not in t:
                problems.append(f"missing threshold block: {key}")

        det = t.get("detection", {})
        if det:
            if det.get("fbr_min_db", 0) <= det.get("estimator_floor_db", -99):
                problems.append(
                    "detection.fbr_min_db must sit above estimator_floor_db, otherwise the "
                    "claim is frozen at the point where the estimator stops working")
            if det.get("snr_vs_noise_min_db", 0) < 10:
                problems.append(
                    "detection.snr_vs_noise_min_db below 10 dB means the measurement could "
                    "be instrument-limited rather than acoustically limited")

        dirn = t.get("direction", {})
        if dirn and dirn.get("correct_direction_min", 0) <= 0.5:
            problems.append("direction.correct_direction_min at or below chance")

        acc = t.get("accuracy", {})
        trk = t.get("tracking", {})
        if acc and trk:
            min_disp = trk.get("min_displacement_m", 0)
            prec = acc.get("displacement_precision_max_m", 1)
            if min_disp < 3 * prec:
                problems.append(
                    f"tracking.min_displacement_m ({min_disp}) is less than 3x "
                    f"accuracy.displacement_precision_max_m ({prec}): a qualifying track "
                    "could be indistinguishable from estimator noise")
            if acc.get("position_rms_max_m", 0) < prec:
                problems.append(
                    "accuracy.position_rms_max_m is tighter than the per-estimate "
                    "precision: accuracy against truth cannot beat the estimator")

        rep = t.get("repeatability", {})
        if rep and rep.get("min_preparations", 0) < 3:
            problems.append(
                "repeatability.min_preparations below 3 cannot separate between-preparation "
                "variance from within-preparation variance")
        return problems

    # -- cost -------------------------------------------------------------------
    def trial_counts(self) -> dict[str, dict[str, Any]]:
        """Turn each rate threshold into the number of acquisitions that could test it."""
        t = self.raw["thresholds"]
        alpha = float(self.raw.get("statistics", {}).get("alpha", 0.05))
        out: dict[str, dict[str, Any]] = {}

        fa = t["detection"]["false_alarm_max"]
        out["candidate_false_alarm"] = {
            "threshold": fa,
            "n_trials_zero_failures": n_for_upper_bound(fa, 0, alpha),
            "n_trials_one_failure": n_for_upper_bound(fa, 1, alpha),
            "meaning": ("mechanism-absent matched-background acquisitions needed before a "
                        "false-alarm ceiling this low can be claimed"),
        }

        dfa = t["direction"]["direction_false_alarm_max"]
        out["direction_false_alarm"] = {
            "threshold": dfa,
            "n_trials_zero_failures": n_for_upper_bound(dfa, 0, alpha),
            "n_trials_one_failure": n_for_upper_bound(dfa, 1, alpha),
            "meaning": ("antegrade and no-flow control events needed before a retrograde "
                        "false-alarm ceiling this low can be claimed"),
        }

        cd = t["direction"]["correct_direction_min"]
        cdl = t["direction"]["correct_direction_lower_bound"]
        out["correct_direction"] = {
            "threshold": cd,
            "lower_bound_required": cdl,
            "n_trials": n_for_lower_bound(cd, cdl, alpha),
            "meaning": ("qualified retrograde events needed for the observed rate to have a "
                        "lower confidence bound above the floor"),
        }
        return out

    def summary(self) -> dict[str, Any]:
        return {
            "version": self.raw.get("version"),
            "frozen_on": self.raw.get("frozen_on"),
            "status": self.raw.get("status"),
            "hash": self.short_hash,
            "problems": self.validate(),
            "trial_counts": self.trial_counts(),
        }
