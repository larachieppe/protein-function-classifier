"""Where to put the two observation points.

The direction claim rests entirely on observing the same attributed feature at two
registered positions in the correct temporal order.  The separation between those
positions is squeezed from both sides:

  lower bound   the arrival-time difference must be resolvable against onset-timing
                uncertainty, otherwise the order is a coin flip;
  upper bound   the feature must still be recognisable when it arrives, so the transit
                time cannot exceed its lifetime;
  hard bound    the surveyed ureter segment is only so long in an 18-24 month child, and
                a single-element bench observes two fixed points, not a field.

Both soft bounds scale with the feature speed, which is unmeasured across nearly two
decades.  The consequence is the central scheduling result of this model: a single fixed
separation cannot serve the whole uncertainty range, and the bench must measure feature
lifetime before the dynamic two-position test is designed.
"""

from __future__ import annotations

import math

import numpy as np


def min_separation_timing(v: np.ndarray, sigma_onset_s: float, k_sigma: float = 3.0) -> np.ndarray:
    """Smallest separation whose arrival-time difference beats onset-timing noise.

        dx >= k * v * sigma_onset
    """
    return k_sigma * np.asarray(v, dtype=float) * sigma_onset_s


def max_separation_lifetime(v: np.ndarray, lifetime_s: np.ndarray,
                            survive_frac: float = 1.0) -> np.ndarray:
    """Largest separation the feature can cross while still recognisable."""
    return np.asarray(v, dtype=float) * np.asarray(lifetime_s, dtype=float) * survive_frac


def min_separation_acoustic(axial_res: float, beamwidth: float, n_cells: float = 5.0) -> float:
    """Smallest separation for which the two range gates do not share clutter.

    Two gates closer than a few resolution cells see the same reverberation and the same
    wall echoes, so an apparent "propagation" between them can be produced by a single
    local change.
    """
    return max(n_cells * axial_res, 2.0 * beamwidth)


def recommended_separation(v: np.ndarray, sigma_onset_s: float, lifetime_s: np.ndarray,
                           k_sigma: float = 3.0) -> np.ndarray:
    """Geometric mean of the two soft bounds: maximally robust to being wrong about v.

    dx = v * sqrt(k * sigma_onset * lifetime).  Note it scales with v, which is exactly
    why a fixed separation is the wrong design choice while v is unmeasured.
    """
    return np.asarray(v, dtype=float) * np.sqrt(k_sigma * sigma_onset_s
                                                * np.asarray(lifetime_s, dtype=float))


def feasible(v: np.ndarray, sigma_onset_s: float, lifetime_s: np.ndarray,
             axial_res: float, beamwidth: float, segment_length: np.ndarray,
             k_sigma: float = 3.0) -> dict:
    """Intersect every constraint and report where a workable separation exists.

    The timing and lifetime bounds both scale with v, so their ratio does not:
    a workable separation exists whenever lifetime > k * sigma_onset, *independently of
    the feature speed*.  The speed only sets where in the window to put the points.
    """
    lo_t = min_separation_timing(v, sigma_onset_s, k_sigma)
    lo_a = min_separation_acoustic(axial_res, beamwidth)
    lo = np.maximum(lo_t, lo_a)
    hi = np.minimum(max_separation_lifetime(v, lifetime_s), np.asarray(segment_length, dtype=float))
    ok = lo <= hi
    rec = np.clip(recommended_separation(v, sigma_onset_s, lifetime_s, k_sigma), lo, hi)
    return {
        "min_separation_m": lo,
        "max_separation_m": hi,
        "recommended_m": np.where(ok, rec, np.nan),
        "feasible": ok,
        "feasible_fraction": float(np.mean(ok)),
        "binding_low": np.where(lo_t >= lo_a, "timing", "acoustic"),
        "lifetime_criterion_s": k_sigma * sigma_onset_s,
    }


def direction_confusion_probability(v_true: np.ndarray, separation_m: float,
                                    sigma_onset_s: float) -> np.ndarray:
    """Probability the arrival order is observed backwards.

    With independent onset-time errors at each position, the difference has std
    sqrt(2)*sigma_onset, and the order flips when that error exceeds the true transit
    time.  This is the floor on wrong-direction rate imposed by timing alone, before any
    artefact, and it is what sets the frozen correct-direction threshold's feasibility.
    """
    v = np.maximum(np.asarray(v_true, dtype=float), 1e-9)
    transit = separation_m / v
    z = np.atleast_1d(transit / (math.sqrt(2.0) * sigma_onset_s))
    # Normal tail via erfc, without scipy
    out = 0.5 * np.asarray([math.erfc(zi / math.sqrt(2.0)) for zi in z.ravel()])
    return out.reshape(z.shape) if np.ndim(transit) else float(out[0])


def separation_for_direction_error(v: float, sigma_onset_s: float, p_max: float) -> float:
    """Separation needed to hold the timing-only wrong-direction probability below p_max.

    Inverts the tail: dx = v * sqrt(2) * sigma_onset * z(p_max).
    """
    # inverse normal tail by bisection (no scipy dependency)
    lo, hi = 0.0, 20.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        p = 0.5 * math.erfc(mid / math.sqrt(2.0))
        if p > p_max:
            lo = mid
        else:
            hi = mid
    z = 0.5 * (lo + hi)
    return v * math.sqrt(2.0) * sigma_onset_s * z
