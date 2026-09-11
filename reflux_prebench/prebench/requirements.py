"""Inverse analysis: turn the link budget into targets the bench can actually measure.

A forward model that says "M2 might be anywhere from -14 dB to -2900 dB" is not an
experimental specification.  The useful direction is the inverse one: given the frozen
detection threshold, what must be *true of the target* for the mechanism to clear it, and
is that quantity something the bench can measure directly?

Each function here returns a requirement expressed in the units of a bench measurement,
so that the answer is falsifiable rather than merely uncertain.
"""

from __future__ import annotations

import math

import numpy as np

from . import acoustics as ac
from .mechanisms import Conditions

FLOOR_DB = -200.0


def clamp(x: np.ndarray, floor: float = FLOOR_DB) -> np.ndarray:
    return np.maximum(np.asarray(x, dtype=float), floor)


def detect_fraction(fbr_db: np.ndarray, threshold_db: float) -> float:
    """Fraction of the sampled uncertainty space in which the mechanism clears threshold.

    This is a statement about the *width of our ignorance*, not a probability that reflux
    is detectable.  The priors are deliberately flat or log-flat over brackets nobody has
    measured, so this number must never be reported as a sensitivity.
    """
    return float(np.mean(np.asarray(fbr_db, dtype=float) >= threshold_db))


# ---------------------------------------------------------------------------
# M1: minimum urine backscatter coefficient
# ---------------------------------------------------------------------------

def required_bsc(cond: Conditions, threshold_db: float, capture_loss_db: float = 0.0) -> np.ndarray:
    """Smallest urine backscatter coefficient that clears the threshold.

    Inverts  E/E_plane = BSC * dz * Omega  against the background and attenuation.
    The bench measures BSC directly from a gate placed wholly inside the fluid, so this
    is a hard, checkable target expressed in the units a backscatter measurement produces.
    """
    needed_db = cond.background_db + threshold_db + cond.attenuation_db + capture_loss_db
    ratio = 10.0 ** (needed_db / 10.0)
    return ratio / (cond.gate_length * cond.solid_angle)


def bsc_noise_floor(cond: Conditions, noise_floor_db: float) -> np.ndarray:
    """Smallest BSC the instrument could even *measure*, given its noise floor.

    If required_bsc is below this, the day-one instrument cannot close M1 either way: a
    null result would be an instrument statement, not a urine statement.
    """
    needed_db = noise_floor_db + cond.attenuation_db
    ratio = 10.0 ** (needed_db / 10.0)
    return ratio / (cond.gate_length * cond.solid_angle)


# ---------------------------------------------------------------------------
# M2: required sharpness-fraction product
# ---------------------------------------------------------------------------

def required_fG(cond: Conditions, threshold_db: float, capture_loss_db: float = 0.0) -> np.ndarray:
    """Required value of the product f * G(k, L_edge) for the fluid-gradient mechanism.

    f is the fraction of the impedance step carried in the leading edge and G is the
    profile factor of that edge.  Both are measurable: f from calibrated concentration
    imaging, G from the measured edge width plus a declared profile shape.  Their product
    is the single number that decides M2, so the bench should report it as one quantity
    with its own uncertainty rather than reporting two and multiplying them silently.
    """
    r_total = ac.r_p_from_dsg(cond.dsg, cond.dc_drho, cond.rho_urine, cond.c_urine)
    needed_db = cond.background_db + threshold_db + cond.attenuation_db + capture_loss_db
    r_needed = 10.0 ** (needed_db / 20.0)
    return r_needed / r_total


def fG_infeasible_fraction(cond: Conditions, threshold_db: float,
                           capture_loss_db: float = 0.0) -> float:
    """Fraction of the space in which the mechanism is impossible, not merely demanding.

    f is a fraction of an impedance step and G is a suppression factor, so their product
    cannot exceed 1.  Wherever the required product exceeds 1 the mechanism cannot clear
    the threshold under *any* profile, and reporting a percentage above 100 would hide
    that.
    """
    return float(np.mean(required_fG(cond, threshold_db, capture_loss_db) > 1.0))


def max_edge_width(cond: Conditions, threshold_db: float, f_sharp: float,
                   capture_loss_db: float = 0.0, shape: str = "tanh") -> np.ndarray:
    """Largest leading-edge width that still clears threshold, at a stated sharp fraction.

    Solved numerically because the profile factor is not analytically invertible.  The
    answer changes by a factor of 3-5 across the three declared profile shapes, which is
    why the shape has to be measured rather than chosen.
    """
    need = required_fG(cond, threshold_db, capture_loss_db) / f_sharp
    # need > 1 means no edge width works at this sharp fraction: report NaN, not a floor.
    impossible = need > 1.0
    need = np.clip(need, 1e-12, 1.0)
    k = cond.k
    lo = np.full_like(need, 1e-7)
    hi = np.full_like(need, 1e-2)
    for _ in range(60):
        mid = np.sqrt(lo * hi)
        g = ac.profile_factor(k, mid, shape)
        too_wide = g < need
        hi = np.where(too_wide, mid, hi)
        lo = np.where(too_wide, lo, mid)
    return np.where(impossible, np.nan, np.sqrt(lo * hi))


# ---------------------------------------------------------------------------
# M4/M5: displacement and geometry requirements
# ---------------------------------------------------------------------------

def min_lumen_opening_for_contrast(cond: Conditions, contrast_db: float = 6.0) -> np.ndarray:
    """Lumen separation at which the two wall surfaces stop cancelling.

    Amplitude ~ 2|r| sin(k h): the opening becomes visible once k h is large enough that
    the pair no longer cancels.  Below this the mechanism is invisible no matter how
    strong the wall echo is, because the two surfaces destructively interfere.
    """
    target = 10.0 ** (-abs(contrast_db) / 20.0)  # fraction of the 2|r| maximum
    return np.arcsin(np.clip(target, 0.0, 1.0)) / cond.k


def motion_rejection_required(reflux_displacement_m: float, resp_excursion_m: np.ndarray,
                              probe_drift_m: float = 1e-3) -> np.ndarray:
    """dB of common-mode motion rejection needed before wall motion can be attributed."""
    nuisance = np.sqrt(np.asarray(resp_excursion_m, dtype=float) ** 2 + probe_drift_m**2)
    return 20.0 * np.log10(nuisance / reflux_displacement_m)


# ---------------------------------------------------------------------------
# Frequency optimisation, per mechanism
# ---------------------------------------------------------------------------

def sweep_frequency(mechanism, cond_factory, f_grid: np.ndarray, threshold_db: float) -> dict:
    """Detectable fraction and median FBR versus centre frequency.

    Frequency trades three ways and differently per mechanism:
      * attenuation rises linearly with f over a two-way path of several centimetres,
      * a graded fluid edge is suppressed once k*L > 1, so higher f hurts M2 twice,
      * diffuse scattering rises as f^4 until 2kL > 1, so higher f helps M3 until it does not.
    There is therefore no single optimum frequency for the programme, only one per
    mechanism, and the day-one element has to be chosen knowing which mechanism it favours.
    """
    med, frac, p90 = [], [], []
    for f0 in f_grid:
        cond = cond_factory(f0)
        res = mechanism.evaluate(cond, threshold_db)
        fbr = clamp(res.fbr_db)
        med.append(float(np.median(fbr)))
        p90.append(float(np.percentile(fbr, 90)))
        frac.append(detect_fraction(res.fbr_db, threshold_db))
    return {
        "f_hz": np.asarray(f_grid, dtype=float),
        "median_fbr_db": np.asarray(med),
        "p90_fbr_db": np.asarray(p90),
        "detect_fraction": np.asarray(frac),
    }


def frequency_exponent_resolution(f_lo: float, f_hi: float, sigma_db: float = 1.0) -> float:
    """Uncertainty on a measured frequency exponent n, given per-band-edge amplitude error.

    Energy ~ f^n, so n = (dB difference) / (10 log10(f_hi/f_lo)).  With two independent
    band-edge estimates each uncertain by sigma_db, sigma_n = sqrt(2)*sigma_db / (10 log10 ratio).

    Measuring n to better than ~0.5 separates specular (n=0) from diffuse (n=4) outright,
    which is the cheapest mechanism discriminator available and needs only bandwidth.
    """
    return math.sqrt(2.0) * sigma_db / (10.0 * math.log10(f_hi / f_lo))
