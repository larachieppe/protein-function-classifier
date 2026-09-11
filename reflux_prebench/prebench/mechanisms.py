"""Six candidate mechanisms, modelled separately and never summed into one number.

Each mechanism carries its own echo-formation law, its own frequency dependence, its
own null prediction, and its own falsifying bench result.  They are deliberately not
combined: they have different physics and different failure modes, and a composite
hypothesis must not be used to rescue a component that failed on its own.

The frequency exponent n (return energy ~ f^n before attenuation) is recorded for each
mechanism because measuring it over a wide band is the cheapest way the bench can tell
the mechanisms apart:

    M1 volume scatter      n ~ 0 to 4  (Rayleigh if scatterers << wavelength)
    M2 fluid gradient      n = 0 with a sharpness roll-off (falls fast once kL > 1)
    M3 diffuse mixing      n = 4 with a roll-off once 2kL > 1
    M4 lumen opening       n = 0, modulated by sin^2(kh) two-surface interference
    M5 wall motion         n = 0 in amplitude; the information is displacement
    M6 composite           interval, not a value
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from . import acoustics as ac
from .uncertain import Q, Status


@dataclass
class Conditions:
    """One sampled state of the world.  Arrays are Monte Carlo draws of equal length."""

    f0: np.ndarray            # centre frequency (Hz)
    bandwidth: np.ndarray     # -6 dB bandwidth (Hz)
    c_tissue: np.ndarray
    c_urine: np.ndarray
    rho_urine: np.ndarray
    z_urine: np.ndarray
    z_wall: np.ndarray
    dc_drho: np.ndarray
    alpha: np.ndarray         # dB/cm/MHz
    depth: np.ndarray         # m
    aperture: np.ndarray      # m
    dsg: np.ndarray
    edge_width: np.ndarray
    sharp_fraction: np.ndarray
    bsc_urine: np.ndarray
    mix_corr_length: np.ndarray
    mix_z_variance: np.ndarray
    lumen_open: np.ndarray
    lumen_collapsed: np.ndarray
    background_db: np.ndarray  # dB re perfect reflector
    profile_shape: str = "tanh"
    mix_spectrum: str = "kolmogorov"
    clutter_suppression_db: np.ndarray | float = 0.0

    @property
    def k(self) -> np.ndarray:
        return ac.wavenumber(self.f0, self.c_urine)

    @property
    def axial_res(self) -> np.ndarray:
        return ac.axial_resolution(self.c_tissue, self.bandwidth)

    @property
    def gate_length(self) -> np.ndarray:
        return self.axial_res

    @property
    def solid_angle(self) -> np.ndarray:
        return ac.receive_solid_angle(self.aperture, self.depth)

    @property
    def attenuation_db(self) -> np.ndarray:
        return ac.attenuation_db(self.depth, self.f0, self.alpha)


@dataclass
class MechanismResult:
    """Echo strength ledger for one mechanism under one set of conditions."""

    key: str
    intrinsic_db: np.ndarray       # dB re perfect reflector, before propagation
    propagated_db: np.ndarray      # after two-way attenuation
    fbr_db: np.ndarray             # relative to declared background
    tolerable_capture_db: np.ndarray
    notes: dict = field(default_factory=dict)


@dataclass
class Mechanism:
    key: str
    name: str
    physical_claim: str
    freq_exponent: str
    null_prediction: str
    falsifier: str
    closes_when: str
    does_not_close: str
    controls: tuple[str, ...]
    strength_fn: Callable[[Conditions], np.ndarray]  # -> intrinsic dB re perfect reflector
    load_bearing_unknowns: tuple[str, ...] = ()

    def evaluate(self, cond: Conditions, threshold_db: float = -10.0) -> MechanismResult:
        intrinsic = np.asarray(self.strength_fn(cond), dtype=float)
        propagated = intrinsic - cond.attenuation_db
        # Clutter filtering only helps a mechanism whose signature is motion against a
        # stationary background, and the programme's own simulations found the benefit
        # small (~5 dB) with SVD filtering capable of removing signal outright.
        fbr = propagated - (cond.background_db - np.asarray(cond.clutter_suppression_db, dtype=float))
        tol = ac.tolerable_capture_loss(
            propagated, cond.background_db - np.asarray(cond.clutter_suppression_db, dtype=float),
            threshold_db)
        return MechanismResult(self.key, intrinsic, propagated, fbr, tol)


# ---------------------------------------------------------------------------
# M1 -- native distributed backscatter (the VFI branch)
# ---------------------------------------------------------------------------

def _m1_volume_scatter(c: Conditions) -> np.ndarray:
    ratio = ac.volume_scatter_ratio(c.bsc_urine, c.gate_length, c.solid_angle)
    return ac.db(ratio)


M1 = Mechanism(
    key="M1",
    name="Native distributed backscatter",
    physical_claim=(
        "Cells, crystals, debris or bubbles suspended in urine scatter enough energy back "
        "to the aperture to form a moving speckle field, as red cells do in blood."),
    freq_exponent="0 to 4 (Rayleigh if scatterers are much smaller than a wavelength)",
    null_prediction=(
        "Gate placed wholly inside homogeneous flowing urine returns nothing above the "
        "electronic noise floor at maximum usable gain."),
    falsifier=(
        "Uniform clean fluid, gate entirely inside the fluid, no wall in the gate: "
        "measured return indistinguishable from the terminated-receiver record."),
    closes_when=(
        "Bulk-fluid return is below the electronic noise floor after the maximum "
        "legitimate coherent averaging, in the most favourable geometry, while the "
        "seeded-particle positive control at a known concentration is recovered in the "
        "same session with the same settings."),
    does_not_close=(
        "Nothing about the other five mechanisms. A urine with no distributed scatter can "
        "still reflect at a boundary with a second fluid or at an opening lumen wall."),
    controls=("uniform clean fluid", "seeded particle ladder", "terminated receiver",
              "pre-trigger record"),
    strength_fn=_m1_volume_scatter,
    load_bearing_unknowns=("bsc_urine",),
)


# ---------------------------------------------------------------------------
# M2 -- urine-urine impedance gradient
# ---------------------------------------------------------------------------

def _m2_fluid_gradient(c: Conditions) -> np.ndarray:
    r_total = ac.r_p_from_dsg(c.dsg, c.dc_drho, c.rho_urine, c.c_urine)
    r_eff = ac.composite_edge_r_p(r_total, c.sharp_fraction, c.k, c.edge_width, c.profile_shape)
    return ac.db(ac.reflected_intensity(r_eff))


M2 = Mechanism(
    key="M2",
    name="Urine-urine impedance gradient",
    physical_claim=(
        "Refluxing urine and resident urine differ in density and sound speed, so the "
        "transition between them reflects."),
    freq_exponent="0 for a step; falls steeply once k*L_edge > 1",
    null_prediction=(
        "Acoustically matched fluids in motion produce no stable feature attributable to a "
        "fluid-fluid gradient, only apparatus and wall residuals."),
    falsifier=(
        "Matched-fluid flow control returns a feature at the same gate, gain and geometry "
        "as the mismatched pair: the echo was never the gradient."),
    closes_when=(
        "No gradient-attributable echo at dSG = 0.016 in the most favourable controlled "
        "geometry, with the stationary mismatched interface confirming in the same session "
        "that the chain can see a boundary at all."),
    does_not_close=(
        "The lumen-opening and wall-motion mechanisms, which do not require any fluid-fluid "
        "contrast. Failure only at dSG = 0.002 closes nothing except the low-contrast corner "
        "and does NOT identify which VUR grades would be missed."),
    controls=("matched fluids flowing", "stationary mismatched interface",
              "moving mismatched interface", "full dSG ladder"),
    strength_fn=_m2_fluid_gradient,
    load_bearing_unknowns=("dc_drho", "sharp_fraction", "edge_width"),
)


# ---------------------------------------------------------------------------
# M3 -- diffuse mixing / turbulence
# ---------------------------------------------------------------------------

def _m3_diffuse(c: Conditions) -> np.ndarray:
    """Diffuse return under the declared mixing-spectrum model.

    ``Conditions.mix_spectrum`` selects "gaussian" or "kolmogorov".  They differ by tens
    of dB once the mixing scale exceeds a wavelength, so the choice is reported alongside
    every M3 number and M3 may not be closed on the Gaussian model alone.
    """
    # RMS impedance fluctuation inside the mixing zone, as a fraction of the bulk step
    sigma_z = c.mix_z_variance * ac.delta_z_over_z(c.dsg, c.dc_drho, c.rho_urine, c.c_urine)
    if c.mix_spectrum == "kolmogorov":
        bsc = ac.diffuse_bsc_powerlaw(c.k, sigma_z, c.mix_corr_length,
                                      inner_scale=c.mix_corr_length / 100.0)
    else:
        bsc = ac.diffuse_bsc(c.k, sigma_z, c.mix_corr_length)
    ratio = ac.volume_scatter_ratio(bsc, c.gate_length, c.solid_angle)
    return ac.db(ratio)


M3 = Mechanism(
    key="M3",
    name="Diffuse mixing / turbulence",
    physical_claim=(
        "Refluxing urine mixing with resident urine creates a random field of small "
        "impedance inhomogeneities that scatter diffusely."),
    freq_exponent="4, rolling off once 2*k*L_corr > 1",
    null_prediction=(
        "Angular response is broad and flat rather than peaked; return scales with "
        "aperture area; matched fluids in turbulent flow return nothing."),
    falsifier=(
        "Matched fluids driven at the same Reynolds number produce the same return: the "
        "signal was hydrodynamic apparatus noise, not composition mixing."),
    closes_when=(
        "No return above the matched-fluid turbulent control across the whole dSG band at "
        "the flow rates the voiding waveform actually produces."),
    does_not_close=(
        "The coherent mechanisms. A diffuse null is expected wherever the transition stays "
        "laminar, so a null here is a statement about the flow regime as much as about "
        "acoustics."),
    controls=("matched fluids at matched Reynolds number", "laminar vs turbulent flow ladder",
              "aperture-area scaling test", "frequency-exponent measurement"),
    strength_fn=_m3_diffuse,
    load_bearing_unknowns=("mix_z_variance", "mix_corr_length", "dc_drho"),
)


# ---------------------------------------------------------------------------
# M4 -- lumen opening
# ---------------------------------------------------------------------------

def _m4_lumen_opening(c: Conditions) -> np.ndarray:
    r_single = np.abs(ac.r_p(c.z_urine * 1e6, c.z_wall * 1e6))
    amp_open = ac.two_surface_response(c.k, c.lumen_open, r_single, c.axial_res)
    amp_closed = ac.two_surface_response(c.k, c.lumen_collapsed, r_single, c.axial_res)
    # The tracked observable is the CHANGE produced by opening, not the static return.
    amp_change = np.abs(amp_open - amp_closed)
    return ac.db(amp_change**2)


M4 = Mechanism(
    key="M4",
    name="Lumen opening",
    physical_claim=(
        "An apposed or nearly apposed ureter is separated by the arriving reflux, creating "
        "a fluid-filled lumen with two wall-fluid surfaces where there was effectively one."),
    freq_exponent="0, modulated by sin^2(k*h) two-surface interference until h exceeds the "
                  "axial resolution",
    null_prediction=(
        "A wall-less channel and a compliant collapsible channel, run under identical flow, "
        "pressure, acoustic and background conditions, return the same waveform."),
    falsifier=(
        "The compliant-channel minus wall-less difference is zero: no wall-mediated "
        "contribution exists at this geometry."),
    closes_when=(
        "A controlled collapsible tube driven through a full opening cycle produces no "
        "repeatable moving RF feature in the most favourable controlled geometry, with "
        "synchronised optical imaging confirming the lumen actually opened."),
    does_not_close=(
        "How often a child's ureter is apposed when reflux begins. That prevalence is "
        "unmeasured and this mechanism is conditional on it. A positive result here is not "
        "evidence of a urine-urine interface."),
    controls=("wall-less channel", "compliant collapsible channel", "pressure-only wall",
              "synchronised optical lumen-area truth"),
    strength_fn=_m4_lumen_opening,
    load_bearing_unknowns=("lumen_collapsed", "z_wall"),
)


# ---------------------------------------------------------------------------
# M5 -- ureter-wall motion
# ---------------------------------------------------------------------------

def _m5_wall_motion(c: Conditions) -> np.ndarray:
    """Amplitude of the wall echo itself.

    This mechanism has the *strongest* echo and the *weakest* specificity: the quantity
    that carries reflux information is the displacement of a strong existing echo, not
    its amplitude.  Its budget is therefore a motion-rejection budget, computed in
    ``wall_motion_rejection_db``.
    """
    r_single = np.abs(ac.r_p(c.z_urine * 1e6, c.z_wall * 1e6))
    return ac.db(ac.reflected_intensity(r_single))


def wall_motion_rejection_db(signal_displacement: np.ndarray,
                             nuisance_displacement: np.ndarray) -> np.ndarray:
    """Common-mode rejection needed to see wall motion caused by reflux.

    Breathing and probe drift move the same strong wall echo by millimetres; the reflux
    contribution may be tens of micrometres.  The ratio is the rejection the motion
    correction must supply before the mechanism can be claimed at all.
    """
    return 20.0 * np.log10(np.asarray(nuisance_displacement, dtype=float)
                           / np.maximum(np.asarray(signal_displacement, dtype=float), 1e-12))


M5 = Mechanism(
    key="M5",
    name="Ureter-wall motion",
    physical_claim=(
        "Reflux displaces, distends or deforms the ureter wall, and the wall echo is strong, "
        "so the displacement of that echo is trackable."),
    freq_exponent="0 in amplitude; the information is carried by displacement, not energy",
    null_prediction=(
        "Under pressure-only actuation with no reflux, the wall echo still moves. The "
        "reflux-specific component is the ordered retrograde propagation of that motion, "
        "not its presence."),
    falsifier=(
        "Imposed rigid-body fixture translation and pump vibration reproduce the same "
        "tracked displacement signature: the feature was apparatus motion."),
    closes_when=(
        "Retrograde wall-motion sequences cannot be separated from simulated antegrade "
        "peristalsis, fixture translation and pump vibration at the frozen decision "
        "threshold."),
    does_not_close=(
        "The fluid mechanisms. Note also that this mechanism is the one most likely to "
        "succeed on the bench and fail clinically, because the bench has no breathing, no "
        "bladder contraction and no operator hand tremor."),
    controls=("pressure-only compliant wall", "rigid-body fixture translation",
              "pump vibration", "simulated antegrade peristalsis"),
    strength_fn=_m5_wall_motion,
    load_bearing_unknowns=("z_wall",),
)


# ---------------------------------------------------------------------------
# M6 -- composite wall-fluid
# ---------------------------------------------------------------------------

def composite_interval_db(a_db: np.ndarray, b_db: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Coherent sum of two contributions with unknown relative phase.

    Returns (worst, best) in dB.  The width of this interval is the point: combining two
    mechanisms with an unknown phase relationship can make the return *weaker* than the
    stronger component alone.  A composite hypothesis therefore cannot be used to rescue a
    component that failed on its own.
    """
    a = 10.0 ** (np.asarray(a_db, dtype=float) / 20.0)
    b = 10.0 ** (np.asarray(b_db, dtype=float) / 20.0)
    lo = np.abs(a - b)
    hi = a + b
    return ac.db(lo**2), ac.db(hi**2)


def _m6_composite(c: Conditions) -> np.ndarray:
    """Pessimistic (destructive) corner of the wall + fluid composite."""
    lo, _hi = composite_interval_db(_m4_lumen_opening(c), _m2_fluid_gradient(c))
    return lo


M6 = Mechanism(
    key="M6",
    name="Composite wall-fluid change",
    physical_claim=(
        "A real reflux event combines lumen opening, a composition gradient, mixing and wall "
        "displacement, and the received waveform is their coherent sum."),
    freq_exponent="undefined: the sum of terms with different exponents and unknown phases",
    null_prediction=(
        "None available. A composite hypothesis makes no null prediction of its own, which "
        "is precisely why it must not be tested first."),
    falsifier=(
        "Not independently falsifiable. It can only be evaluated after its components have "
        "been measured separately."),
    closes_when=(
        "Never on its own. This mechanism is closed only by the closure of every component, "
        "and it is opened only by evidence that two measured components co-occur with a "
        "stable phase relationship."),
    does_not_close=(
        "Anything. The destructive corner of the composite interval is weaker than the "
        "strongest component alone, so a composite claim cannot rescue a failed component."),
    controls=("all component controls, run first",),
    strength_fn=_m6_composite,
    load_bearing_unknowns=("relative phase (entirely unconstrained)",),
)


ALL: tuple[Mechanism, ...] = (M1, M2, M3, M4, M5, M6)
BY_KEY = {m.key: m for m in ALL}
