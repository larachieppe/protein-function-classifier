"""Displacement estimation: precision bounds, sampling, PRF, and decorrelation.

This module answers the parts of the experimental specification that concern the
*estimator* rather than the target: how much bandwidth, how fast to sample, how fast to
pulse, and how large the resulting position and speed errors are.

The headline pre-bench result produced here is negative in a useful way: cross-
correlation precision is not the binding constraint anywhere in the plausible operating
space.  Bandwidth is set by clutter separation, and the position-error budget is
consumed by registration and motion, not by the estimator.
"""

from __future__ import annotations

import math

import numpy as np


# ---------------------------------------------------------------------------
# Time-delay estimation precision
# ---------------------------------------------------------------------------

def crlb_delay_std(
    window_s: float | np.ndarray,
    f_lo: float | np.ndarray,
    f_hi: float | np.ndarray,
    rho: float | np.ndarray,
    snr_amp: float | np.ndarray,
) -> np.ndarray:
    """Cramer-Rao lower bound on time-delay estimation std (Walker & Trahey, 1995).

        sigma_tau^2 >= 3 / (2 pi^2 T (f_hi^3 - f_lo^3)) * [ (1/rho^2)(1 + 1/SNR^2)^2 - 1 ]

    ``window_s``  correlation window duration (s)
    ``f_lo/f_hi`` -6 dB band edges (Hz)
    ``rho``       correlation coefficient between the two acquisitions
    ``snr_amp``   echo amplitude SNR (linear, not dB)

    The bracket blows up as rho falls, which is the honest statement that decorrelation,
    not noise, is what destroys a displacement estimate.
    """
    window_s = np.asarray(window_s, dtype=float)
    rho = np.clip(np.asarray(rho, dtype=float), 1e-3, 0.999999)
    snr_amp = np.maximum(np.asarray(snr_amp, dtype=float), 1e-6)
    band = np.asarray(f_hi, dtype=float) ** 3 - np.asarray(f_lo, dtype=float) ** 3
    bracket = (1.0 / rho**2) * (1.0 + 1.0 / snr_amp**2) ** 2 - 1.0
    bracket = np.maximum(bracket, 0.0)
    var = 3.0 * bracket / (2.0 * math.pi**2 * window_s * band)
    return np.sqrt(var)


def delay_to_displacement(sigma_tau: np.ndarray, c: float) -> np.ndarray:
    """Axial displacement error from a delay error: dx = c * dtau / 2."""
    return c * np.asarray(sigma_tau, dtype=float) / 2.0


def velocity_std(sigma_x: np.ndarray, dt: float) -> np.ndarray:
    """Two independent position estimates differenced over dt."""
    return math.sqrt(2.0) * np.asarray(sigma_x, dtype=float) / dt


def min_fbr_for_precision(sigma_x_target: float, c: float, window_s: float,
                          f_lo: float, f_hi: float, rho: float) -> float:
    """Lowest feature-to-background ratio at which a position-error budget is met.

    This is a *precision* floor and it is independent of the detection threshold.  If it
    sits above the estimator's own working floor, then the interval between them is a
    regime where a feature is detectable and trackable but its displacement cannot be
    measured to the declared accuracy -- which must be reported as indeterminate rather
    than quietly accepted.
    """
    lo, hi = -60.0, 60.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        st = crlb_delay_std(window_s, f_lo, f_hi, rho, snr_amp_from_fbr_db(mid))
        if float(delay_to_displacement(st, c)) > sigma_x_target:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def snr_amp_from_fbr_db(fbr_db: float | np.ndarray) -> np.ndarray:
    """Feature-to-background ratio in dB (energy) -> amplitude ratio."""
    return 10.0 ** (np.asarray(fbr_db, dtype=float) / 20.0)


# ---------------------------------------------------------------------------
# Pulse-repetition frequency: three competing constraints
# ---------------------------------------------------------------------------

def prf_max_range(depth_max: float, c: float, guard: float = 1.25) -> float:
    """Upper bound: the previous echo must die before the next pulse.

    PRF_max = c / (2 * d_max * guard).  The guard factor covers ring-down and
    reverberation tails that arrive after the nominal deepest echo.
    """
    return c / (2.0 * depth_max * guard)


def prf_min_phase(v_max: float, f0: float, c: float, frac_lambda: float = 0.25) -> float:
    """Lower bound for phase-domain tracking: motion per pulse below lambda/4.

    Beyond lambda/4 per pulse the correlation peak becomes ambiguous between cycles.
    """
    lam = c / f0
    return v_max / (frac_lambda * lam)


def prf_min_window(v_max: float, window_len_m: float, frac_window: float = 0.25) -> float:
    """Lower bound for envelope/window tracking: motion per pulse below a fraction of
    the correlation window, so that successive windows still overlap."""
    return v_max / (frac_window * window_len_m)


def prf_min_track(n_frames: int, feature_lifetime_s: float) -> float:
    """Lower bound from the frozen minimum track length: N qualified frames must fit
    inside the feature's lifetime."""
    return n_frames / feature_lifetime_s


def prf_feasible(depth_max: float, v_max: float, f0: float, c: float,
                 window_len_m: float, n_frames: int, lifetime_s: float,
                 phase_domain: bool = True) -> dict:
    """Intersect every PRF constraint and report whether a window exists."""
    hi = prf_max_range(depth_max, c)
    lo_motion = (prf_min_phase(v_max, f0, c) if phase_domain
                 else prf_min_window(v_max, window_len_m))
    lo_track = prf_min_track(n_frames, lifetime_s)
    lo = max(lo_motion, lo_track)
    return {
        "prf_max_range_hz": hi,
        "prf_min_motion_hz": lo_motion,
        "prf_min_track_hz": lo_track,
        "prf_min_hz": lo,
        "feasible": bool(lo <= hi),
        "margin_db": float(10.0 * math.log10(hi / lo)) if lo > 0 else float("inf"),
        "domain": "phase" if phase_domain else "window",
    }


# ---------------------------------------------------------------------------
# Sampling rate: measured, not asserted
# ---------------------------------------------------------------------------

def subsample_bias_experiment(
    f0: float,
    frac_bw: float,
    samples_per_cycle: np.ndarray,
    true_shifts: np.ndarray | None = None,
    rng: np.random.Generator | None = None,
    snr_db: float = 60.0,
) -> dict:
    """Measure parabolic sub-sample interpolation bias versus oversampling.

    Generates a Gabor pulse, shifts it by a known sub-sample amount, cross-correlates,
    fits a parabola to the peak, and records the error.  The required sampling rate is
    then read off the curve rather than assumed from a rule of thumb.

    ``snr_db`` defaults high so that the measured quantity is interpolation *bias*, which
    is what the sampling rate controls.  Estimator noise is bounded separately by the
    Cramer-Rao calculation and does not improve with oversampling past Nyquist.
    """
    rng = rng or np.random.default_rng(20260910)
    true_shifts = np.linspace(-0.5, 0.5, 21) if true_shifts is None else true_shifts
    bw = frac_bw * f0
    out_bias, out_rms = [], []

    for spc in samples_per_cycle:
        fs = spc * f0
        n = 4096
        t = (np.arange(n) - n / 2) / fs
        sigma_t = 1.0 / (math.pi * bw)  # Gabor envelope for the -6 dB bandwidth
        errs = []
        for s in true_shifts:
            shift_s = s / fs
            base = np.exp(-(t**2) / (2 * sigma_t**2)) * np.cos(2 * math.pi * f0 * t)
            shifted = np.exp(-((t - shift_s) ** 2) / (2 * sigma_t**2)) * np.cos(
                2 * math.pi * f0 * (t - shift_s))
            noise = 10 ** (-snr_db / 20.0)
            a = base + noise * rng.standard_normal(n)
            b = shifted + noise * rng.standard_normal(n)
            xc = np.correlate(b - b.mean(), a - a.mean(), mode="same")
            k = int(np.argmax(xc))
            if k <= 0 or k >= n - 1:
                continue
            y0, y1, y2 = xc[k - 1], xc[k], xc[k + 1]
            denom = y0 - 2 * y1 + y2
            frac = 0.0 if denom == 0 else 0.5 * (y0 - y2) / denom
            est = (k - n // 2) + frac
            errs.append(est - s)
        errs_arr = np.asarray(errs)
        out_bias.append(float(np.max(np.abs(errs_arr))))
        out_rms.append(float(np.sqrt(np.mean(errs_arr**2))))

    return {
        "samples_per_cycle": np.asarray(samples_per_cycle, dtype=float),
        "peak_abs_error_samples": np.asarray(out_bias),
        "rms_error_samples": np.asarray(out_rms),
    }


def required_fs(f_hi: float, samples_per_cycle_at_f0: float, f0: float) -> float:
    """Sampling rate must satisfy Nyquist for the top of the band *and* the
    interpolation-bias requirement at the centre frequency."""
    return max(2.5 * f_hi, samples_per_cycle_at_f0 * f0)


def bias_to_displacement_m(err_samples: np.ndarray, fs: np.ndarray, c: float) -> np.ndarray:
    """Convert an interpolation error in samples into an axial displacement error."""
    return c * np.asarray(err_samples, dtype=float) / (2.0 * np.asarray(fs, dtype=float))


# ---------------------------------------------------------------------------
# Dynamic range and quantisation
# ---------------------------------------------------------------------------

def processing_gain_db(fs: float, bandwidth: float) -> float:
    """Oversampling processing gain after matched filtering."""
    return 10.0 * math.log10(max(fs / (2.0 * bandwidth), 1.0))


def averaging_gain_db(n_avg: int) -> float:
    """Coherent averaging of N pulses against uncorrelated noise.

    Only legitimate for *stationary* configurations.  A moving or deforming feature is
    blurred by averaging, so the moving-feature measurement must live on instantaneous
    dynamic range alone.
    """
    return 10.0 * math.log10(max(n_avg, 1))


def required_enob(dynamic_range_db: float, fs: float, bandwidth: float,
                  n_avg: int = 1, margin_db: float = 6.0) -> float:
    """Effective number of bits needed to span a required dynamic range.

        DR_available = 6.02*ENOB + 1.76 + processing gain + averaging gain
    """
    available_from_bits = dynamic_range_db + margin_db - processing_gain_db(fs, bandwidth) \
        - averaging_gain_db(n_avg)
    return (available_from_bits - 1.76) / 6.02


def thermal_noise_v(bandwidth: float, r_source: float = 50.0, temp_k: float = 300.0,
                    noise_figure_db: float = 2.0) -> float:
    """RMS thermal noise voltage of the receive chain over the signal bandwidth."""
    k_b = 1.380649e-23
    v2 = 4.0 * k_b * temp_k * r_source * bandwidth
    return math.sqrt(v2) * 10 ** (noise_figure_db / 20.0)


# ---------------------------------------------------------------------------
# Decorrelation budget
# ---------------------------------------------------------------------------

def decorrelation_from_translation(dx: float | np.ndarray, beamwidth: float) -> np.ndarray:
    """Correlation lost when the feature translates laterally by dx within the beam.

    Gaussian beam overlap model: rho = exp(-(dx/beamwidth)^2 * 4 ln2).
    """
    dx = np.asarray(dx, dtype=float)
    return np.exp(-((dx / beamwidth) ** 2) * 4.0 * math.log(2.0))


def decorrelation_from_elevation(dy: float | np.ndarray, slice_thickness: float) -> np.ndarray:
    """Out-of-plane loss.  Distinct from in-plane error: it removes the feature from the
    measurement entirely rather than biasing it."""
    return decorrelation_from_translation(dy, slice_thickness)


def frames_to_decorrelate(v_lateral: float, beamwidth: float, prf: float,
                          rho_min: float = 0.5) -> float:
    """How many pulses before correlation falls below rho_min from lateral drift."""
    if v_lateral <= 0:
        return float("inf")
    dx_allowed = beamwidth * math.sqrt(-math.log(rho_min) / (4.0 * math.log(2.0)))
    return dx_allowed / v_lateral * prf
