"""Core acoustics: impedance, reflection, graded profiles, beams, attenuation.

All echo strengths in this package are expressed in dB relative to a *perfect planar
reflector at the focus* (r_p = 1, normal incidence, no attenuation).  That reference is
chosen because it is the one quantity a bench can measure on day one with a steel or
quartz plate, which makes every number here falsifiable by a single calibration
measurement rather than by an absolute pressure calculation nobody can check.

Symbol         Meaning
-----------    --------------------------------------------------------------
Z              acoustic impedance, rho * c                       [Rayl]
r_p            pressure-amplitude reflection coefficient         [-]
R_I            reflected-intensity fraction, |r_p|^2             [-]
G(k, L)        profile factor for a graded (non-step) transition [-]
L_capture      energy not collected by the aperture              [dB]
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

ArrayLike = float | np.ndarray


# ---------------------------------------------------------------------------
# Basic relations
# ---------------------------------------------------------------------------

def impedance(rho: ArrayLike, c: ArrayLike) -> ArrayLike:
    """Z = rho * c."""
    return rho * c


def r_p(z1: ArrayLike, z2: ArrayLike) -> ArrayLike:
    """Pressure-amplitude reflection coefficient at normal incidence."""
    return (z2 - z1) / (z2 + z1)


def reflected_intensity(rp: ArrayLike) -> ArrayLike:
    """R_I = |r_p|^2.  An amplitude ratio is not an energy ratio."""
    return np.abs(rp) ** 2


def db(x: ArrayLike) -> ArrayLike:
    """Power/energy ratio to dB."""
    return 10.0 * np.log10(np.maximum(np.asarray(x, dtype=float), 1e-300))


def db_amp(x: ArrayLike) -> ArrayLike:
    """Amplitude ratio to dB."""
    return 20.0 * np.log10(np.maximum(np.asarray(x, dtype=float), 1e-300))


def undb(x: ArrayLike) -> ArrayLike:
    return 10.0 ** (np.asarray(x, dtype=float) / 10.0)


def wavelength(f: ArrayLike, c: ArrayLike) -> ArrayLike:
    return c / f


def wavenumber(f: ArrayLike, c: ArrayLike) -> ArrayLike:
    return 2.0 * math.pi * f / c


# ---------------------------------------------------------------------------
# Specific gravity -> impedance contrast
# ---------------------------------------------------------------------------

def delta_z_over_z(dsg: ArrayLike, dc_drho: ArrayLike, rho: ArrayLike, c: ArrayLike) -> ArrayLike:
    """Relative impedance contrast produced by a specific-gravity difference.

    Z = rho*c, so

        dZ/Z = drho/rho + dc/c
             = dSG/SG + (dc/drho)*drho/c
             = dSG * (1 + (dc/drho) * rho / c)          [SG ~ 1, drho = dSG * 1000]

    The bracketed multiplier is the whole reason specific gravity is not an acoustic
    variable.  Across the declared dc_drho bracket it ranges over roughly 1.3 - 2.4,
    i.e. a factor of ~1.8 in amplitude and ~5 dB in energy, before any geometry.
    """
    rho_w = 1000.0  # density of water, the SG reference
    drho = np.asarray(dsg, dtype=float) * rho_w
    return drho / rho + dc_drho * drho / c


def r_p_from_dsg(dsg: ArrayLike, dc_drho: ArrayLike, rho: ArrayLike, c: ArrayLike) -> ArrayLike:
    """Weak-contrast reflection coefficient for a urine-urine step: r_p ~ dZ/(2 Z)."""
    return delta_z_over_z(dsg, dc_drho, rho, c) / 2.0


# ---------------------------------------------------------------------------
# Graded transitions: the profile factor
# ---------------------------------------------------------------------------

def profile_factor(k: ArrayLike, L: ArrayLike, shape: str = "tanh") -> ArrayLike:
    """Amplitude suppression of a graded impedance transition of width scale L.

    In the weak-scattering (Born) limit the reflection coefficient is the Fourier
    transform of the impedance gradient evaluated at twice the wavenumber:

        r(k) = 1/2 * integral d(ln Z)/dz * exp(-2 i k z) dz

    so the answer depends on the *shape* assumed for the transition, not only on its
    width.  Three declared conventions:

      tanh      Z varies as tanh(z/L); r = r0 * (pi k L) / sinh(pi k L).
                L is a 1/e-like scale, the transition is ~4L wide end to end.
      linear    Z ramps linearly over total width L; r = r0 * sinc(k L).
      gaussian  Gradient is Gaussian with std L; r = r0 * exp(-2 (k L)^2).

    These disagree by a factor of 3-5 in the width that survives a given budget.  That
    disagreement is a pre-bench finding: the bench must measure the profile shape, not
    only a width, before any sharpness rule can be applied.
    """
    k = np.asarray(k, dtype=float)
    L = np.asarray(L, dtype=float)
    u = k * L
    if shape == "tanh":
        x = math.pi * u
        # x/sinh(x), stable at x -> 0 and x -> large
        out = np.where(x < 1e-6, 1.0 - x * x / 6.0, x / np.sinh(np.minimum(x, 700.0)))
        return np.where(x > 700.0, 0.0, out)
    if shape == "linear":
        return np.sinc(u / math.pi)  # np.sinc(y) = sin(pi y)/(pi y)
    if shape == "gaussian":
        return np.exp(-2.0 * u * u)
    raise ValueError(f"unknown profile shape {shape!r}")


def composite_edge_r_p(
    r_total: ArrayLike,
    f_sharp: ArrayLike,
    k: ArrayLike,
    edge_width: ArrayLike,
    shape: str = "tanh",
) -> ArrayLike:
    """Reflection from a composite profile: a sharp leading edge on a broad tail.

    A fraction ``f_sharp`` of the total impedance step is carried inside a leading edge
    of width ``edge_width``; the remaining (1 - f_sharp) is spread over a mixing zone
    wide enough to contribute nothing at this wavenumber.  This is the only profile
    family in which a mixed transition can still return a compact echo.
    """
    return r_total * f_sharp * profile_factor(k, edge_width, shape)


# ---------------------------------------------------------------------------
# Two-surface (lumen) interference
# ---------------------------------------------------------------------------

def two_surface_response(k: ArrayLike, h: ArrayLike, r_single: ArrayLike,
                         axial_res: ArrayLike | None = None) -> ArrayLike:
    """Coherent pressure amplitude returned by two parallel wall-fluid surfaces.

    Front wall returns +r, back wall returns -r (impedance step reverses sign), delayed
    by 2h/c.  Amplitude = |r| * |1 - exp(-2 i k h)| = 2|r| |sin(k h)|.

    Consequences that matter for the lumen-opening mechanism:
      * h -> 0 (apposed lumen): the two surfaces cancel; a collapsed ureter returns
        almost nothing beyond the outer wall.  The *opening* is therefore the signal.
      * k h = pi/2 (h = lambda/4): the pair adds in phase, +6 dB over a single surface.
      * h > axial resolution: the surfaces are separately resolved and no longer
        interfere; the model switches to incoherent addition (factor sqrt(2)).
    """
    k = np.asarray(k, dtype=float)
    h = np.asarray(h, dtype=float)
    coherent = 2.0 * np.abs(r_single) * np.abs(np.sin(k * h))
    if axial_res is None:
        return coherent
    resolved = math.sqrt(2.0) * np.abs(r_single) * np.ones_like(coherent)
    return np.where(h > np.asarray(axial_res, dtype=float), resolved, coherent)


# ---------------------------------------------------------------------------
# Volume and diffuse scattering
# ---------------------------------------------------------------------------

def volume_scatter_ratio(bsc: ArrayLike, gate_length: ArrayLike, solid_angle: ArrayLike) -> ArrayLike:
    """Energy from a resolution cell of distributed scatterers, relative to a perfect
    planar reflector at the same range.

        E_vol / E_plane = BSC * dz * Omega_receive

    where dz is the axial gate length (c*tau/2) and Omega = A_aperture / d^2 is the
    solid angle the aperture subtends.  This is the quantity that decides whether
    native-urine VFI is physically possible; nothing about it is currently measured.
    """
    return np.asarray(bsc, dtype=float) * gate_length * solid_angle


def diffuse_bsc(k: ArrayLike, sigma_z: ArrayLike, corr_length: ArrayLike) -> ArrayLike:
    """Backscatter coefficient of a random impedance field (Born, Gaussian correlation).

        BSC(k) = (k^4 / (4 pi^2)) * Phi(2k),
        Phi(K) = sigma_z^2 * L^3 * pi^(3/2) * exp(-K^2 L^2 / 4)

    The k^4 dependence (falling away once 2kL > 1) is the signature that separates a
    diffuse mixing return from a specular one, which is frequency-flat.  Measuring the
    frequency exponent is the cheapest mechanism discriminator the bench has.
    """
    k = np.asarray(k, dtype=float)
    L = np.asarray(corr_length, dtype=float)
    sz2 = np.asarray(sigma_z, dtype=float) ** 2
    phi = sz2 * L**3 * math.pi**1.5 * np.exp(-((2.0 * k) ** 2) * L**2 / 4.0)
    return (k**4 / (4.0 * math.pi**2)) * phi


def diffuse_bsc_powerlaw(k: ArrayLike, sigma_z: ArrayLike, outer_scale: ArrayLike,
                         inner_scale: ArrayLike | None = None, beta: float = 11.0 / 3.0) -> ArrayLike:
    """Backscatter from a turbulent impedance field with a power-law (Kolmogorov) spectrum.

        Phi(K) = A * sigma_z^2 * L0^3 * (1 + (K L0)^2)^(-beta/2) * exp(-(K l0)^2)

    A Gaussian correlation model has almost no spectral content above K ~ 1/L, so it
    predicts essentially zero backscatter whenever the mixing scale exceeds a wavelength.
    Real turbulence does not behave that way: a power-law cascade keeps feeding structure
    down to the inner (viscous) scale, and backscatter at 2k survives far longer.

    The two models disagree by tens of dB in exactly the regime that matters.  Closing the
    diffuse mechanism on the strength of a Gaussian assumption would therefore be a
    modelling artefact, not a measurement.  The discriminator is the measured frequency
    exponent: Gaussian rolls off abruptly, a power law does not.
    """
    k = np.asarray(k, dtype=float)
    L0 = np.asarray(outer_scale, dtype=float)
    sz2 = np.asarray(sigma_z, dtype=float) ** 2
    K = 2.0 * k
    norm = math.gamma(beta / 2.0) / (math.gamma((beta - 3.0) / 2.0) * math.pi ** 1.5)
    phi = norm * sz2 * L0**3 * (1.0 + (K * L0) ** 2) ** (-beta / 2.0)
    if inner_scale is not None:
        phi = phi * np.exp(-((K * np.asarray(inner_scale, dtype=float)) ** 2))
    return (k**4 / (4.0 * math.pi**2)) * phi


# ---------------------------------------------------------------------------
# Propagation and capture
# ---------------------------------------------------------------------------

def attenuation_db(depth: ArrayLike, f_hz: ArrayLike, alpha_db_cm_mhz: ArrayLike) -> ArrayLike:
    """Two-way soft-tissue attenuation in dB (energy)."""
    depth_cm = np.asarray(depth, dtype=float) * 100.0
    f_mhz = np.asarray(f_hz, dtype=float) / 1e6
    return 2.0 * alpha_db_cm_mhz * depth_cm * f_mhz


def axial_resolution(c: ArrayLike, bandwidth: ArrayLike) -> ArrayLike:
    """-6 dB axial resolution ~ c / (2 * B) for a pulse of bandwidth B."""
    return c / (2.0 * np.asarray(bandwidth, dtype=float))


def lateral_beamwidth(f: ArrayLike, c: ArrayLike, f_number: ArrayLike) -> ArrayLike:
    """-6 dB lateral beamwidth at focus ~ 1.02 * lambda * F#."""
    return 1.02 * wavelength(f, c) * f_number


def depth_of_field(f: ArrayLike, c: ArrayLike, f_number: ArrayLike) -> ArrayLike:
    """-6 dB depth of field ~ 7.1 * lambda * F#^2 (standard focused-aperture result)."""
    return 7.1 * wavelength(f, c) * np.asarray(f_number, dtype=float) ** 2


def specular_lobe_fwhm(f: ArrayLike, c: ArrayLike, illuminated_width: ArrayLike) -> ArrayLike:
    """Angular FWHM (radians) of the mirror lobe from a flat reflector of finite width.

    A tilted specular surface returns its energy into a lobe of angular width ~lambda/D.
    If the angular sweep step is coarser than this, the bench can step straight over the
    peak and wrongly close the mechanism.
    """
    return wavelength(f, c) / np.asarray(illuminated_width, dtype=float)


def receive_solid_angle(aperture_diameter: ArrayLike, depth: ArrayLike) -> ArrayLike:
    area = math.pi * (np.asarray(aperture_diameter, dtype=float) / 2.0) ** 2
    return area / np.asarray(depth, dtype=float) ** 2


# ---------------------------------------------------------------------------
# Reconciliation with the inherited link budget
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class InheritedBudget:
    """The DOC-TECH Table 10 tolerable-capture-loss table, and what it implies."""

    empty_fill: tuple[float, float, float] = (46.7, 36.7, 26.7)
    dsg_016: tuple[float, float, float] = (40.5, 30.5, 20.5)
    dsg_002: tuple[float, float, float] = (22.5, 12.5, 2.5)
    threshold_db: float = -10.0
    r_p_empty_fill: float = 0.032


def recover_inherited_backgrounds(budget: InheritedBudget | None = None) -> tuple[float, float, float]:
    """Recover the background levels the inherited table never stated.

    The table reports tolerable capture loss L for each mechanism/background pair.  By
    construction L = signal_dB - background_dB + |threshold|, so

        background_dB = signal_dB + |threshold| - L

    Applying this to the empty-fill row (whose r_p = 0.032 is stated) recovers the three
    background levels as -66.6 / -56.6 / -46.6 dB re a perfect reflector.  Those three
    numbers were doing all the work in the inherited budget and were never visible.
    """
    b = budget or InheritedBudget()
    sig = float(db(reflected_intensity(b.r_p_empty_fill)))
    return tuple(sig + abs(b.threshold_db) - L for L in b.empty_fill)  # type: ignore[return-value]


def recover_inherited_dc_drho(budget: InheritedBudget | None = None,
                              rho: float = 1010.0, c: float = 1540.0) -> float:
    """Recover the dc/drho the inherited table implicitly assumed.

    The dSG = 0.016 row sits a fixed number of dB below the empty-fill row.  Inverting
    r_p = dSG*(1 + (dc/drho)*rho/c)/2 against that offset gives the implied constant.
    It comes out at about 1.47 (m/s)/(kg/m^3) -- a salt-dominated composition.  Urine is
    urea-dominated, so the inherited budget may be optimistic by several dB.
    """
    b = budget or InheritedBudget()
    backgrounds = recover_inherited_backgrounds(b)
    # tolerable loss L = 10log10(r^2) + |thr| - bg  ->  r = 10^((L + bg - |thr|)/20)
    r016 = 10.0 ** ((b.dsg_016[0] + backgrounds[0] - abs(b.threshold_db)) / 20.0)
    mult = 2.0 * r016 / 0.016
    return (mult - 1.0) * c / rho


def tolerable_capture_loss(signal_db: ArrayLike, background_db: ArrayLike,
                           threshold_db: float = -10.0) -> ArrayLike:
    """dB of capture loss a mechanism can absorb before it falls below the estimator.

    L_tolerable = signal - background + |threshold|
    """
    return np.asarray(signal_db, dtype=float) - np.asarray(background_db, dtype=float) + abs(threshold_db)
