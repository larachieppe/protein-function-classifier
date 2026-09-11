"""Derive the instrument specification from the frozen claim and the mechanism models.

Nothing in this module is chosen by preference.  Each number is the output of a stated
constraint, and where two constraints conflict the conflict is reported rather than
averaged away.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import acoustics as ac
from . import estimator as est


@dataclass
class Requirement:
    """One derived number, with the constraint that produced it."""

    quantity: str
    value: float
    units: str
    driver: str
    detail: str = ""

    def fmt(self) -> str:
        v = self.value
        if abs(v) >= 1e6:
            txt = f"{v/1e6:.3g} M"
        elif abs(v) >= 1e3:
            txt = f"{v/1e3:.3g} k"
        elif abs(v) < 1e-3 and v != 0:
            txt = f"{v:.3g} "
        else:
            txt = f"{v:.4g} "
        return f"{txt}{self.units}"


@dataclass
class InstrumentSpec:
    requirements: list[Requirement] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)

    def add(self, *a, **kw) -> Requirement:
        r = Requirement(*a, **kw)
        self.requirements.append(r)
        return r

    def get(self, quantity: str) -> Requirement:
        for r in self.requirements:
            if r.quantity == quantity:
                return r
        raise KeyError(quantity)


# ---------------------------------------------------------------------------
# Bandwidth
# ---------------------------------------------------------------------------

def bandwidth_requirements(c: float, lumen_open_min: float, wall_sep_min: float,
                           edge_target: float, f_lo: float, f_hi: float,
                           sigma_db: float = 1.0) -> dict:
    """Four independent bandwidth drivers, reported separately.

    1. resolve the two walls of an open lumen                 B >= c / (2 * h_open)
    2. separate the feature from the nearest wall echo        B >= c / (2 * d_sep)
    3. resolve the leading edge as a distinct structure       B >= c / (2 * L_edge)
    4. measure the frequency exponent to a useful precision   set by the band ratio

    Driver 3 is the most demanding by an order of magnitude and is also the least
    necessary: the edge does not have to be resolved for its echo to be detected and
    tracked.  Reporting them separately prevents the hardest constraint from silently
    becoming the specification.
    """
    return {
        "resolve_open_lumen_hz": c / (2.0 * lumen_open_min),
        "separate_from_wall_hz": c / (2.0 * wall_sep_min),
        "resolve_leading_edge_hz": c / (2.0 * edge_target),
        "exponent_sigma": est_exponent_sigma(f_lo, f_hi, sigma_db),
        "band_ratio": f_hi / f_lo,
    }


def est_exponent_sigma(f_lo: float, f_hi: float, sigma_db: float = 1.0) -> float:
    return math.sqrt(2.0) * sigma_db / (10.0 * math.log10(f_hi / f_lo))


def bandwidth_for_position_error(sigma_x_target: float, c: float, f0: float,
                                 window_s: float, rho: float, fbr_db: float) -> float:
    """Fractional bandwidth needed to hit a position-error target at a stated FBR.

    Solves the Walker-Trahey bound for the band edges, assuming a symmetric band about
    f0.  Reported so that the specification can state explicitly how much margin the
    estimator has, rather than assuming precision is the binding constraint.
    """
    snr = est.snr_amp_from_fbr_db(fbr_db)
    sigma_tau = 2.0 * sigma_x_target / c
    bracket = (1.0 / rho**2) * (1.0 + 1.0 / snr**2) ** 2 - 1.0
    need_cube = 3.0 * bracket / (2.0 * math.pi**2 * window_s * sigma_tau**2)
    # f_hi^3 - f_lo^3 with f_hi = f0(1+b/2), f_lo = f0(1-b/2)
    lo, hi = 1e-4, 2.0
    for _ in range(200):
        b = 0.5 * (lo + hi)
        val = (f0 * (1 + b / 2)) ** 3 - (f0 * (1 - b / 2)) ** 3
        if val < need_cube:
            lo = b
        else:
            hi = b
    return 0.5 * (lo + hi)


# ---------------------------------------------------------------------------
# Depth coverage
# ---------------------------------------------------------------------------

def depth_coverage(focus: float, f_number: float, f0: float, c: float) -> tuple[float, float]:
    """-6 dB depth of field of a fixed-focus element, as a depth interval."""
    dof = ac.depth_of_field(f0, c, f_number)
    return focus - dof / 2.0, focus + dof / 2.0


def elements_needed(depth_lo: float, depth_hi: float, f_number: float, f0: float,
                    c: float) -> list[tuple[float, float, float]]:
    """Tile the required depth sweep with fixed-focus elements.

    Returns (focus, near, far) for each element.  The programme's provisional element
    (42 mm focus, f/3.0) covers one tile; the required sweep spans the distal, mid and
    proximal routes, so the number of tiles is a purchasing decision this model makes
    explicit rather than leaving to a later surprise.
    """
    dof = float(ac.depth_of_field(f0, c, f_number))
    span = depth_hi - depth_lo
    n = max(1, math.ceil(span / dof - 1e-9))
    step = span / n
    out: list[tuple[float, float, float]] = []
    for i in range(n):
        near = depth_lo + i * step
        far = near + step
        out.append((near + step / 2.0, near, far))
    return out


# ---------------------------------------------------------------------------
# Angular and aperture sweep design
# ---------------------------------------------------------------------------

def angular_sweep(f0: float, c: float, illuminated_width: float,
                  span_deg: float = 40.0, samples_per_fwhm: float = 3.0) -> dict:
    """Design the angle sweep so a specular peak cannot be stepped over.

    A flat reflector of illuminated width D returns into a lobe of angular FWHM ~lambda/D.
    Sampling coarser than that lobe can miss the peak entirely and produce a false
    negative that looks like a closed mechanism.
    """
    fwhm = ac.specular_lobe_fwhm(f0, c, illuminated_width)
    step = math.degrees(fwhm) / samples_per_fwhm
    n = int(math.ceil(2.0 * span_deg / step)) + 1
    return {
        "specular_fwhm_deg": math.degrees(fwhm),
        "max_step_deg": step,
        "span_deg": span_deg,
        "n_angles": n,
        "note": ("A diffuse return is broad and flat; a specular return is this narrow. "
                 "Sweeping coarser than max_step risks closing a live mechanism."),
    }


def aperture_discriminator(apertures_m: np.ndarray, depth: float) -> dict:
    """Predicted aperture scaling for specular vs diffuse returns.

    A diffuse return collects energy in proportion to aperture area (+6 dB per doubling
    of diameter); a specular return that already misses the aperture does not improve at
    all.  Running the aperture ladder at a fixed angle is therefore a second, independent
    mechanism discriminator that costs one afternoon.
    """
    a = np.asarray(apertures_m, dtype=float)
    diffuse_db = 20.0 * np.log10(a / a[0])
    return {
        "apertures_m": a,
        "diffuse_prediction_db": diffuse_db,
        "specular_prediction_db": np.zeros_like(a),
        "separation_db": diffuse_db,
    }


# ---------------------------------------------------------------------------
# Receiver chain
# ---------------------------------------------------------------------------

def dynamic_range_requirement(strongest_echo_db: float, weakest_required_db: float,
                              headroom_db: float = 6.0) -> float:
    """Instantaneous dynamic range between the largest in-gate echo and the smallest
    measurement the claim requires, both referenced to a perfect reflector."""
    return (strongest_echo_db - weakest_required_db) + headroom_db


def receiver_spec(dr_db: float, fs: float, bandwidth: float, n_avg_static: int,
                  reference_echo_v: float = 1.0) -> dict:
    """Digitiser and noise requirements for the moving-feature case.

    A moving or deforming feature cannot be coherently averaged without blurring it, so
    the moving-feature measurement must be carried by instantaneous dynamic range.  The
    static configurations may average, which is why two ENOB numbers are reported.
    """
    enob_moving = est.required_enob(dr_db, fs, bandwidth, n_avg=1)
    enob_static = est.required_enob(dr_db, fs, bandwidth, n_avg=n_avg_static)
    noise_v = reference_echo_v * 10 ** (-(dr_db) / 20.0)
    return {
        "dynamic_range_db": dr_db,
        "enob_moving_feature": enob_moving,
        "bits_moving_feature": math.ceil(enob_moving + 1.5),
        "enob_static_averaged": enob_static,
        "processing_gain_db": est.processing_gain_db(fs, bandwidth),
        "averaging_gain_db": est.averaging_gain_db(n_avg_static),
        "max_input_noise_v_rms": noise_v,
        "thermal_floor_v_rms": est.thermal_noise_v(bandwidth),
    }
