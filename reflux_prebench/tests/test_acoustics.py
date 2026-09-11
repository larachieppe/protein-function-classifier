"""Validate the physics against numbers published in the programme's own documents.

Pre-bench, there is no measurement to check the model against.  The strongest available
validation is that the model reproduces every quantitative claim in the source documents
from first principles, including the ones those documents state without derivation.
"""

import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from prebench import acoustics as ac


def test_illustrative_fluid_pair():
    """DOC-TECH sec.2.1: Z1=1.500, Z2=1.515 MRayl gives r_p ~ 0.005, R_I ~ 2.5e-5."""
    rp = ac.r_p(1.500e6, 1.515e6)
    assert rp == pytest.approx(0.00497, abs=2e-4)
    assert float(ac.reflected_intensity(rp)) == pytest.approx(2.5e-5, rel=0.05)


def test_urine_tissue_pair():
    """DOC-TECH eq.29-30: Z_urine=1.571, Z_tissue=1.675 gives r_p ~ 0.032, R_I ~ 0.001."""
    rp = ac.r_p(1.571e6, 1.675e6)
    assert rp == pytest.approx(0.032, abs=5e-4)
    assert float(ac.reflected_intensity(rp)) == pytest.approx(0.001, rel=0.05)


def test_amplitude_is_not_energy():
    """DOC-PLAIN sec.2.3: 3.2% pressure amplitude is about 0.1% intensity."""
    assert float(ac.reflected_intensity(0.032)) == pytest.approx(0.001, rel=0.05)


def test_recovers_inherited_backgrounds():
    """The three background levels implied by DOC-TECH Table 10, never stated in it."""
    bgs = ac.recover_inherited_backgrounds()
    assert bgs == pytest.approx((-66.6, -56.6, -46.6), abs=0.05)
    # exactly 10 dB apart, which is what makes them a declared ladder rather than a fit
    assert bgs[1] - bgs[0] == pytest.approx(10.0, abs=0.01)
    assert bgs[2] - bgs[1] == pytest.approx(10.0, abs=0.01)


def test_recovers_inherited_dc_drho():
    """The solute assumption implied by Table 10's dSG rows."""
    v = ac.recover_inherited_dc_drho()
    assert 1.3 < v < 1.7, v


def test_reproduces_table10_within_0p2_db():
    """Every cell of the inherited tolerable-capture-loss table, from first principles."""
    bgs = ac.recover_inherited_backgrounds()
    dcdrho = ac.recover_inherited_dc_drho()
    ib = ac.InheritedBudget()
    cases = [
        (ib.r_p_empty_fill, ib.empty_fill),
        (float(ac.r_p_from_dsg(0.016, dcdrho, 1010.0, 1540.0)), ib.dsg_016),
        (float(ac.r_p_from_dsg(0.002, dcdrho, 1010.0, 1540.0)), ib.dsg_002),
    ]
    for rp, published in cases:
        sig = float(ac.db(ac.reflected_intensity(rp)))
        for bg, want in zip(bgs, published):
            got = float(ac.tolerable_capture_loss(sig, bg))
            assert got == pytest.approx(want, abs=0.2), (rp, bg, got, want)


def test_provisional_element_depth_of_field():
    """DOC-TECH sec.4.3 states a -6 dB depth of field of about 3.2-5.3 cm."""
    dof = float(ac.depth_of_field(5e6, 1540.0, 3.0))
    near, far = 42e-3 - dof / 2, 42e-3 + dof / 2
    assert near == pytest.approx(0.032, abs=0.002)
    assert far == pytest.approx(0.053, abs=0.002)


def test_profile_factor_limits():
    k = ac.wavenumber(5e6, 1540.0)
    for shape in ("tanh", "linear", "gaussian"):
        assert float(ac.profile_factor(k, 1e-12, shape)) == pytest.approx(1.0, abs=1e-6)
        assert abs(float(ac.profile_factor(k, 5e-3, shape))) < 0.2


def test_profile_factor_monotone_in_width():
    k = ac.wavenumber(5e6, 1540.0)
    widths = np.array([1e-6, 1e-5, 3e-5, 1e-4])
    g = ac.profile_factor(k, widths, "tanh")
    assert np.all(np.diff(g) < 0)


def test_profile_conventions_disagree():
    """The reason the bench must measure the shape, not only a width."""
    k = ac.wavenumber(5e6, 1540.0)
    L = 100e-6
    vals = {s: float(ac.profile_factor(k, L, s)) for s in ("tanh", "linear", "gaussian")}
    assert max(vals.values()) / min(vals.values()) > 3.0, vals


def test_two_surface_cancels_when_apposed():
    """An apposed lumen returns almost nothing: the two surfaces cancel."""
    k = ac.wavenumber(5e6, 1540.0)
    peak = 2 * 0.032
    assert float(ac.two_surface_response(k, 1e-9, 0.032)) / peak < 1e-4


def test_two_surface_peaks_at_quarter_wave():
    k = ac.wavenumber(5e6, 1540.0)
    lam = 1540.0 / 5e6
    peak = float(ac.two_surface_response(k, lam / 4, 0.032))
    assert peak == pytest.approx(2 * 0.032, rel=1e-6)


def test_two_surface_is_non_monotonic():
    """Echo amplitude versus opening is non-monotonic: a testable bench prediction."""
    k = ac.wavenumber(5e6, 1540.0)
    h = np.linspace(1e-6, 300e-6, 400)
    amp = ac.two_surface_response(k, h, 0.032)
    d = np.diff(amp)
    assert np.any(d > 0) and np.any(d < 0)


def test_delta_z_multiplier_bracket():
    """dSG -> dZ/Z carries a 1.3-2.4x multiplier across the dc/drho bracket."""
    lo = float(ac.delta_z_over_z(0.01, 0.5, 1010.0, 1540.0)) / 0.01
    hi = float(ac.delta_z_over_z(0.01, 2.2, 1010.0, 1540.0)) / 0.01
    assert 1.25 < lo < 1.4
    assert 2.3 < hi < 2.5


def test_attenuation_two_way():
    """0.5 dB/cm/MHz at 5 MHz over 35 mm, two-way, is 17.5 dB."""
    assert float(ac.attenuation_db(0.035, 5e6, 0.5)) == pytest.approx(17.5, rel=1e-6)


def test_gaussian_and_powerlaw_spectra_disagree_hugely():
    """M3 must not be closed on a Gaussian mixing assumption."""
    k = ac.wavenumber(5e6, 1540.0)
    g = float(ac.diffuse_bsc(k, 1e-2, 500e-6))
    p = float(ac.diffuse_bsc_powerlaw(k, 1e-2, 500e-6, inner_scale=5e-6))
    assert p / max(g, 1e-300) > 1e6
